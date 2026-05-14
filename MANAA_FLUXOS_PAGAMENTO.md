# Manaã — Fluxos de Pagamento e Onboarding

Documentação completa dos fluxos de cadastro, cobrança, ativação e cancelamento do Manaã. Atualizado em 2026-05-14.

## Visão geral arquitetural

```
Frontend (GitHub Pages)
  ↓ POST /api/checkout/init  (pagos)
  ↓ POST /webhook/manaa-onboarding (todos)
Cloudflare Worker (manaa-meta-webhook.manaa-fbx.workers.dev)
  ↓ Proxy HTTP → HTTPS + CORS
n8n (Oracle VM, port 5678, container Docker)
  ├─ Workflow ASAAS Checkout (DhbSR6UYaprNA1pA)
  ├─ Workflow Onboarding Único (manaa-onboarding-1)
  ├─ Workflow ASAAS Eventos (manaa-asaas-hook-1)
  ├─ Workflow Trial Expiry (FJefFAM8DAqZz1W8)
  ├─ Workflow ASAAS Status Check (manaa-asaas-status-1)
  └─ Workflow Whats Diário Devocional (manaa-wpp-dispatch-1)
Postgres (Oracle VM, port 5432, localhost only)
  ├─ assinantes
  ├─ subscriptions
  ├─ payments
  ├─ messages
  ├─ facts
  └─ reengagement_log
ASAAS Sandbox (https://sandbox.asaas.com)
Meta WhatsApp Cloud API (Graph v21)
```

## Planos

| Plano | Preço | Cobrança | Trial | NF |
|-------|-------|----------|-------|-----|
| Trial | R$ 0 | Sem cobrança | 7 dias | Não |
| Mensal | R$ 14,99/mês | PIX Automático OU CC recorrente | — | Sim, cada cobrança |
| Anual | R$ 159,99 único | PIX único OU CC à vista OU CC parcelado 2-12x sem juros | — | Sim, no pagamento (parcelado: 1 NF por parcela) |

## Cenário 1 — Cadastro Trial (free)

```
Usuário acessa /onboarding.html?plano=trial
  ├─ Preenche 4 etapas: perfil, rotina, propósito, plano+LGPD
  └─ Clica "Começar meu teste grátis"
       ↓
Frontend submitForm():
  POST /webhook/manaa-onboarding {nome, phone, religiao, inspiracoes, horario, versao, ocupacao, proposito, plano:trial, lgpd:true}
       ↓
Workflow Onboarding Único:
  1. Validar Payload (aceita aliases phone/lgpd/horario/versao/proposito)
  2. Calcular Perfil (idade → perfil_remember idoso/adulto/jovem; momento_vida vulnerável overrides pra idoso)
  3. UPSERT Assinante (active=true, horario_envio, religiao, inspiracoes, versao_biblica_pref, momento_vida, proposito_espiritual, perfil_remember, lgpd_*)
  4. LLM Pronúncia → Atualizar Pronúncia DB (gpt-4o-mini pronuncia o nome + gênero)
  5. Notificar CEO Telegram (sempre dispara — Luigi recebe notificação)
  6. Trial Gate IF (sempre FALSE) — PULA Enviar Boas-vindas (não dispara template Meta, evita custo)
  7. LLM Extrair Fatos + Salvar Fatos DB (gpt-4o-mini extrai fatos persistentes do propósito/momento/inspirações)
  8. Insert Trial Sub (subscriptions gateway='free', plan_id=3, status='trialing', trial_start=NOW, trial_end=NOW+7d)
  9. Responder OK {ok:true, assinante_id}
       ↓
Frontend redireciona pra /pagamento-sucesso.html?plan=trial
  └─ Mostra "Tudo pronto / Seu teste de 7 dias começou. Amanhã no horário escolhido chega o primeiro devocional."
  └─ Botão wa.me "Continuar no WhatsApp" pré-preenchido com "Oi Manaã 🙏 vamos começar?"
  └─ Auto-abre nova aba em 3s (desktop)

Pessoa CLICA wa.me → abre WhatsApp → envia mensagem → janela 24h aberta no Meta → conversação livre

OBS: Se pessoa NÃO clicar wa.me, assinante continua active no banco. Dispatch matinal D+1 vai disparar TEMPLATE Meta (categoria utility, pago) — pessoa recebe devocional mesmo sem ter conversado antes.
```

## Cenário 2 — Pagamento Anual PIX único

```
Usuário acessa /onboarding.html?plano=anual
  ├─ Preenche 4 etapas (idem trial)
  ├─ Etapa 4: carrossel inicia em Mensal (default), arrasta pra Anual → escolhe "PIX" (R$ 159,99)
  ├─ Preenche email, CPF (valida dígito verificador), CEP, número
  ├─ Aceita LGPD
  └─ Clica "Pagar com PIX"
       ↓
Frontend submitV2():
  (1) POST /webhook/manaa-onboarding (cria assinante igual trial, MAS Trial Gate FALSE pula boas-vindas — pago não envia template tb)
  (2) POST /api/checkout/init → Worker proxy → /webhook/manaa-checkout
       ↓
Workflow ASAAS Checkout (DhbSR6UYaprNA1pA):
  1. Parse Form (normaliza phone E.164, CPF, valores; notificationDisabled=true em sandbox)
  2. Asaas Criar Customer (POST sandbox.asaas.com/api/v3/customers com endereço completo)
  3. UPSERT Assinante (já existe pelo onboarding, atualiza)
  4. Check Existing Sub (idempotência: SELECT subscriptions WHERE assinante_id AND status IN ('active','trialing') OR (pending_authorization < 30min))
  5. Sub Existente? IF — se SIM, pula pra Resposta Existente (idempotente)
  6. Anual? IF (true) → Asaas Criar Payment (POST /v3/payments billingType=PIX value=159.99 invoiceData={service, observations, externalReference})
  7. PIX único? IF (true) → Pegar QR PIX (POST /v3/payments/{id}/pixQrCode)
  8. INSERT Subscription DB (assinante_id, plan_id=2, gateway='asaas', gateway_subscription_id=paymentId, status='pending_authorization')
  9. Resposta Frontend (paymentId, authorizationId=paymentId, invoiceUrl, value, pix:{qrImage, payload, expirationDate})
       ↓
Frontend renderStep5Result:
  └─ Mostra card único: header (Manaã — Plano Anual / R$ 159,99 em Lora dourado), QR Code 220px, botão "Copiar código PIX" (5s reset), separador, "Como pagar em 3 passos" com círculos dourados + ícones SVG (smartphone, QR, check), rodapé "Confirmação automática · QR válido por 24h"
  └─ pollPaymentStatus(authorizationId) inicia: GET /webhook/manaa-asaas-status?id=X a cada 5s, max 150 tentativas (12.5min)

Pessoa paga via banco PIX → ASAAS sandbox auto-confirma:
  ASAAS envia webhook → Cloudflare Worker proxy → /webhook/manaa-asaas-webhook
       ↓
Workflow ASAAS Eventos (manaa-asaas-hook-1):
  1. Webhook Asaas
  2. Parse Event (extrai paymentId, customerId, status; subscriptionId fallback pra paymentId pra Anual)
  3. Switch Evento ASAAS (3 condições OR no caso confirmado):
       - event === PAYMENT_CONFIRMED
       - event === PAYMENT_RECEIVED
       - event === PAYMENT_CREATED AND payment.status === CONFIRMED
  4. DB Pagamento Confirmado (UPDATE subscriptions SET status='active', current_period_end=NOW+30d WHERE gateway IN ('asaas','asaas_pix_auto') AND gateway_subscription_id=$1)
  5. Build NF Body (service description, taxes 0%, municipalServiceCode 01.09.02, customer, payment)
  6. Emitir NF Auto (POST sandbox.asaas.com/api/v3/invoices)
       ↓
Polling do frontend (próximo poll ~5s depois):
  GET /webhook/manaa-asaas-status?id=pay_X → {"status":"active"}
  └─ window.location.href = /pagamento-sucesso.html?plan=anual&id=X
       ↓
Tela final: "Pagamento confirmado / Sua assinatura está ativa" + wa.me "Oi Manaã 🙏 vamos começar?"
```

## Cenário 3 — Pagamento Anual Cartão à vista

```
Idem cenário 2 ATÉ Asaas Criar Payment
  └─ billingType=CREDIT_CARD, installmentCount NÃO setado, creditCard {holderName, number, expiryMonth, expiryYear, ccv}, creditCardHolderInfo {name, email, cpfCnpj, postalCode, addressNumber, phone}, remoteIp
       ↓
ASAAS sandbox aprova SÍNCRONO (cartão de teste 5162306219378829)
  Response: paymentId, status="CONFIRMED" (não PENDING)
       ↓
Frontend detecta data.status === 'CONFIRMED' → window.location.href = /pagamento-sucesso.html (sem passar pelo step 5)
       ↓
Webhook ASAAS chega em ~30-60s (PAYMENT_CREATED com status CONFIRMED) → hook UPDATE subscription pra 'active' + emite NF
```

## Cenário 4 — Pagamento Anual Cartão parcelado 12x

```
Idem cenário 3, MAS installments=12 no Parse Form
  └─ Payload ASAAS: installmentCount=12, totalValue=159.99 (value não setado, ASAAS divide)
       ↓
ASAAS cria UM payment com 12 parcelas
  Cada parcela vira CC charge separada → cada parcela emite NF ao confirmar (12 NFs R$ 13,33 cada)
       ↓
Status CONFIRMED imediato (primeira parcela), redirect direto
```

## Cenário 5 — Pagamento Mensal PIX Automático + consent

```
Usuário acessa /onboarding.html?plano=mensal
  ├─ Etapa 4: card Mensal centralizado, escolhe "PIX Automático" (default)
  ├─ Aceita CONSENT específico ("Entendo que serão debitados R$ 14,99 da minha conta todo mês via PIX Automático")
  ├─ Preenche email, CPF, CEP, número, LGPD
  └─ Clica "Autorizar PIX Automático - R$ 14,99/mês"
       ↓
Workflow ASAAS Checkout:
  Anual? IF (false) → Asaas Criar Subscription (POST /v3/subscriptions billingType=PIX, cycle=MONTHLY, value=14.99, nextDueDate)
  PIX Auto? IF (true) → Listar Payments Sub (GET /v3/subscriptions/{id}/payments) → Pegar QR PIX Sub (POST /v3/payments/{firstPayment}/pixQrCode)
  PIX Auto + consent? IF (true) → INSERT consent_log (assinante_id, type='pix_recurring', ip, user_agent)
  INSERT Subscription DB (gateway='asaas', gateway_subscription_id=sub_xxx, status='pending_authorization')
  Resposta: subscriptionId, firstPaymentId, pix:{qrImage, payload}
       ↓
Frontend renderStep5Result QR (idem Anual)
  pollPaymentStatus(subscriptionId) — frontend prioriza data.subscriptionId pra Mensal
       ↓
Pessoa autoriza no banco → ASAAS envia PIX_AUTOMATIC_RECURRING_AUTHORIZATION_ACTIVATED → hook (Switch caso pix_auto_ativado) → DB PIX Auto Ativado → assinatura ACTIVE
       ↓
Próximos meses: ASAAS auto-cobra dia 14 de cada mês via PIX Auto, sem intervenção do site
```

## Cenário 6 — Pagamento Mensal Cartão recorrente

```
Idem Cenário 5, MAS billingType=CREDIT_CARD na sub ASAAS, creditCard preenchido
  ASAAS aprova primeira cobrança SÍNCRONA → status CONFIRMED imediato
  Próximos meses: ASAAS auto-cobra cartão dia 14
       ↓
Frontend redirect direto pra pagamento-sucesso (sem passar step 5)
```

## Cenário 7 — Idempotência (mesmo phone tenta criar 2ª subscription)

```
Pessoa tenta refazer checkout com phone que JÁ tem subscription ativa/trialing/pending_authorization (recente)
       ↓
Workflow:
  Check Existing Sub → encontra subscription existente
  Sub Existente? IF (true, sem filtro de plano) → Buscar Payment Existente (GET /v3/subscriptions/{id}/payments) → Resposta Existente
  Retorna: {ok:true, idempotent:true, message:"Você já tem uma assinatura ativa", subscriptionId, status, firstPaymentId, invoiceUrl}
       ↓
Frontend detecta data.idempotent === true → window.location.href = /pagamento-sucesso.html?status=existing
  └─ Tela "Você já está com a gente / Sua assinatura do Manaã já está ativa. Continue conversando comigo pelo WhatsApp" + wa.me

PROTECT: Postgres UNIQUE constraint em assinantes.phone_e164 garante 1 assinante por phone. UNIQUE em subscriptions.(gateway, gateway_subscription_id) garante não duplicar sub no banco.
```

## Cenário 8 — Cartão inválido / erro

```
Pessoa clica Pagar com cartão recusado pelo sandbox
       ↓
ASAAS retorna 400 com error "Transação não autorizada"
       ↓
Workflow ASAAS Checkout: nó Asaas Criar Payment com onError continueRegularOutput
  Erro propaga pro Resposta Frontend (ok:false, error:msg)
       ↓
Frontend: card vermelho "Não conseguimos processar o pagamento. Verifique os dados ou tente outra forma." Permanece na etapa 4 pra corrigir.
       ↓
Erros inline embaixo de cada campo problemático (CPF, CC, etc) com mensagem específica.
```

## Cenário 9 — Trial Expirado (cron diário)

```
Workflow Trial Expiry (FJefFAM8DAqZz1W8) — cron 09:00 BR
       ↓
1. Buscar assinantes (Postgres):
   SELECT a.id, a.name, a.phone_e164, s.id AS subscription_id
   FROM assinantes a
   JOIN subscriptions s ON s.assinante_id = a.id
   WHERE s.status='trialing' AND s.trial_end < NOW()
   AND a.active = true
2. Preparar Lista (Code)
3. UPDATE subscriptions SET status='expired'
4. UPDATE assinantes SET active=false (DESATIVA — não recebe mais devocional)
5. Enviar WA CTA template "trial_acabado" via Meta API (botão upgrade pra Mensal ou Anual)
6. INSERT messages (direction='outbound', template_name='trial_acabado')
```

## Cenário 10 — Pagamento atrasado (past_due / overdue) — PENDENTE

```
ASAAS envia webhook PAYMENT_OVERDUE quando cobrança recorrente Mensal falha
       ↓
Workflow ASAAS Eventos:
  Switch caso 'vencido' → DB Pagamento Vencido (UPDATE subscription SET status='past_due')

PENDENTE: Não há workflow ainda que pega past_due e manda CTA de reativação.

PROPOSTA (pós-SLC): adicionar branch no Trial Expiry ou novo workflow "Past Due CTA" que:
  - Busca assinantes com sub.status='past_due' há > 24h
  - Envia template "pagamento_atrasado" com link de reativação (regerar payment ASAAS via API)
```

## Cenário 11 — Cancelamento

```
Pessoa envia "PARAR", "CANCELAR" ou "SAIR" no WhatsApp
       ↓
Workflow META Webhook:
  Comando Especial? IF detecta keyword
  UPDATE assinantes SET cancel_pending_at=NOW (entra em 48h de "estou de saída")
       ↓
Workflow Whats Diário Devocional (cron 30min):
  Filtro: cancel_pending_at < NOW - 48h → para de enviar devocional
  Subscription continua até final do período pago
       ↓
PENDENTE pós-SLC: Magic Link cancelamento pelo portal /conta com token

Cancelamento ASAAS:
  Subscription Mensal: DELETE /v3/subscriptions/{id} → status='canceled' no banco
  Anual: cobrança única, não há renovação. Cancelar = stop devocional + nada de novo pagamento (já cobrado)
```

## Variáveis usadas no AI Agent (system prompt)

Todo Agent IA (META Webhook) usa contexto do assinante:
- `religiao` — Católica / Evangélica / Cristão sem denominação (tom ajustado)
- `versao_biblica_pref` — NVI / ARA / NTLH / etc (versículo conforme)
- `inspiracoes` — Padre Marcelo, Aline Barros, Provérbios (referência sutil)
- `momento_vida` — luto, ansiedade, recomeço, viuvez (sensibilidade)
- `proposito_espiritual` — texto livre (foco)
- `perfil_remember` — idoso (mais carinhoso) / adulto / jovem (mais leve)
- `genero` — concordância no tom (querida/querido)
- `pronuncia_nome` — pronuncia fonética (TTS áudio)

Devocional matinal e Reengajamento Sutil também usam mesmos campos.

## Validação de cenários (Edge real, 2026-05-13)

| Cenário | Status | NF emitida? |
|---------|--------|-------------|
| Trial | ✓ | N/A |
| Anual PIX | ✓ confirmação manual sandbox → webhook auto ~60s | Sim, SCHEDULED→AUTHORIZED |
| Anual CC vista | ✓ CONFIRMED imediato | Sim |
| Anual CC 12x | ✓ CONFIRMED imediato | Sim, 12 NFs R$ 13,33 |
| Mensal PIX Auto | ✓ subscription criada, QR mostrado, polling redireciona após webhook | Sim mensal |
| Mensal CC recorrente | ✓ CONFIRMED imediato | Sim mensal |
| Idempotência | ✓ retorna idempotent, NÃO duplica sub | N/A |
| CC inválido | ✓ erro amigável, fica na etapa 4 | N/A |

## Pendências pré-produção

1. **Cert A1 real** (~R$170/ano) ou Focus NF-e (~R$60/mês) — sandbox usa cert auto-assinado fake
2. **Trocar URL** sandbox.asaas.com → api.asaas.com em 6 nós n8n
3. **Trocar access_token** sandbox → produção em todas creds
4. **Remover** notificationDisabled=true do Parse Form (queremos que ASAAS notifique cliente real por email)
5. **Habilitar webhook ASAAS prod** (configuração de URL/eventos no painel ASAAS prod)
6. **WABA real** (+1 555-938-2375 Manaã) — atual +15551804368 é teste (250 msg/dia limit)
7. **HTTPS no n8n** + bloquear porta 5678 público (hoje exposta)
8. **Past_due CTA** workflow
9. **Magic Link cancelamento** portal /conta
10. **Polling timeout UX** (12.5min hoje, mensagem se passar)
11. **Race condition** assinante_id (pg_advisory_xact_lock) — risco baixo na prática, idempotência atual basta
12. **Trial Engagement Email** se pessoa NÃO clica wa.me — opcional
