# Intelligent Query Format Detection - Debug Guide

## ULTIMO UPDATE (v5) - Structured Query Format (SQF)
L'architettura è stata riprogettata per essere **intelligente e sicura**:
- ✅ Seleziona categoria (Clienti, Prodotti, Ordini, ecc.)
- ✅ Scrivi query in linguaggio naturale
- 🆕 **LLM intelligente**: Decide se serve domain o JSON strutturato
- 🆕 **Zero SQL**: Usa Python + Odoo ORM, mai SQL raw
- 🆕 **Multi-model nativo**: Supporta aggregazioni, exclusioni, conteggi senza SQL

## Il Problema: Domain Limitations

Odoo domains non possono esprimere:
```python
# Query: "Clienti con più di 3 fatture"
# Impossibile in domain:
[('invoices_count', '>', 3)]  ← invoices_count non esiste!
# Domain supporta solo filtri semplici
```

## La Soluzione: Structured Query Format

Invece di forcing la LLM a generare un dominio impossibile, la LLM genera **JSON strutturato** quando serve:

```
Query: "Clienti con più di 3 fatture"
       ↓
LLM decide: "Questo serve COUNT! Non è un dominio semplice"
       ↓
LLM risponde:
{
  "query_type": "count_aggregate",
  "primary_model": "res.partner",
  "secondary_model": "account.move",
  "link_field": "partner_id",
  "threshold": 3,
  "comparison": ">="
}
       ↓
Sistema: "Ho riconosciuto JSON con query_type!"
       ↓
Esegui _execute_count_aggregate_from_spec()
```

## Come Funziona

**File principali**:
- `models/search_query.py`:
  - `_parse_natural_language()`: Comunica con LLM (domain o JSON)
  - `_parse_query_response()`: 🆕 Rileva formato (JSON vs domain)
  - `_execute_structured_query()`: 🆕 Esegue query strutturate
  - `_execute_count_aggregate_from_spec()`: 🆕 Logica aggregazione Python
  - `_execute_exclusion_from_spec()`: 🆕 Logica esclusione Python

**Niente SQL Generator**: Non serve più `sql_generator.py` (opzionale per future extensions)

## Flusso di Esecuzione

```
1. [LLM] Riceve prompt con decision tree
   "Questa query serve multi-model logic? Rispondi JSON o domain"

2. [PARSE-JSON] Tenta parsing JSON
   Se valido E ha query_type → Query strutturata ✓
   Altrimenti → Tenta domain parsing

3. [PARSE-DOMAIN] Tenta parsing domain
   Estrae [('field', 'op', 'value')]

4. [STRUCTURED-EXEC] Se è strutturata:
   - Chiama _execute_count_aggregate_from_spec()
   - O _execute_exclusion_from_spec()
   - Ritorna risultati

5. Oppure esecuzione domain normale
```

## Query Types Supportati

### Count Aggregation
```json
{
  "query_type": "count_aggregate",
  "primary_model": "res.partner",
  "secondary_model": "account.move",
  "link_field": "partner_id",
  "threshold": 3,
  "comparison": ">="
}
```

**Cosa fa**: Conta record di `secondary_model` per ogni `primary_model`, ritorna quelli con count `>= threshold`

**Esempi**:
- "Clienti con più di 3 fatture" → count >= 3
- "Partner con almeno 5 ordini" → count >= 5
- "Fornitori con meno di 2 acquisti" → count < 2

### Exclusion
```json
{
  "query_type": "exclusion",
  "primary_model": "product.template",
  "secondary_model": "sale.order",
  "link_field": "product_id"
}
```

**Cosa fa**: Ritorna `primary_model` records che NON appaiono in `secondary_model`

**Esempi**:
- "Prodotti mai ordinati" → product.template NOT IN sale.order
- "Fornitori senza acquisti" → res.partner NOT IN purchase.order

## Monitoraggio e Debug

### Log Prefix
```
[PARSE-JSON]      → Tentativo parsing JSON
[PARSE-DOMAIN]    → Fallback domain parsing
[STRUCTURED-EXEC] → Esecuzione query strutturata
[STRUCTURED-AGG]  → Fase count aggregation
[STRUCTURED-EXC]  → Fase exclusion
```

**Vedere i log**:
```bash
tail -f /var/log/odoo/odoo.log | grep "PARSE-\|STRUCTURED"
```

### Campi tracciati in search.query

```
query_type = Selection(['simple_domain', 'count_aggregate', 'exclusion'])
query_spec = Text(JSON strutturato)
is_multi_model = Boolean(True se query tipo count_aggregate o exclusion)
used_sql_fallback = Boolean(Future: Reserved per SQL fallback generation)
```

### Testare una query

1. Vai a Ovunque → Query Search
2. Scrivi: "Clienti con più di 3 fatture"
3. Esegui
4. Scorri a "Query Type" → Vedi "Count Aggregation"
5. Scorri a "Query Specification (JSON)" → Vedi il JSON

## Sicurezza

✅ **Zero SQL injection**: Nessun SQL raw  
✅ **Odoo RLS**: Usa sempre ORM, tutte le security rules applicate  
✅ **Auditable**: Ogni azione è loggata da Odoo  
✅ **Validabile**: JSON spec è facilmente inspecionabile  
✅ **Python only**: Codice Python puro, no template SQL

## Soluzioni Implementate

### 1. **Prompt Migliorato** (search_query.py)
- Aggiunto descrizione del modello con `_get_model_description()`
- Aggiunto esempi specifici per ogni modello con `_get_model_examples()`
- Aumentati campi da 20 a 50 in `_get_field_info()`
- Aggiunto prompt più dettagliato e ben strutturato

### 2. **Logging Dettagliato** (search_query.py:79-107, 214-254)
Aggiunti log con prefissi per tracciare il flusso:
- `[LLM]` - Fase di comunicazione con OpenAI
- `[PARSE]` - Fase di parsing del response
- `[REPAIR]` - Tentativi di aggiustamento

## Come Debuggare

### Passo 1: Controllare i log
```
In Odoo → Settings → Technical → Logs
Filtrare per: "[LLM]" o "[PARSE]"
```

### Passo 2: Leggere la "Raw LLM Response"
1. Vai su Ovunque → Query Search
2. Clicca sulla query problematica
3. Scorri in basso a "Debug Info"
4. Leggi il campo "Raw LLM Response"

Se vedi:
- **`[]`** = LLM non ha capito la query
- **Testo lungo** = Response non è una lista Python valida
- **Codice ma con errori** = Syntax error nel dominio

### Passo 3: Verificare il prompt
Nel log (setting "SQL_DEBUG"), cerca `[LLM] Prompt length:` per vedere se è stato costruito correttamente.

## Test SQL Fallback

### Query che attivano SQL (Domain-only fallback)

Queste query non funzionano col dominio puro, attivano SQL:

**Aggregazioni (COUNT)**:
```
"Clienti con più di 10 fatture"
"Partner con 5+ ordini"
"Fornitori con meno di 3 acquisti"
```

**Range queries**:
```
"Prodotti ordinati tra 5 e 20 volte"
"Clienti con fatture tra 1000 e 5000 euro"
```

**Temporal logic**:
```
"Fornitori attivi negli ultimi 6 mesi"
"Clienti non contattati da 1 anno"
```

### Come verificare SQL in produzione

1. **Seleziona una query dal log**:
   ```bash
   grep "Domain returned empty results" /var/log/odoo/odoo.log | tail -1
   ```

2. **Vai nella query in Odoo**:
   - Ovunque → Query Search
   - Clicca sulla query
   - Scroll down a "Generated SQL Query"
   - Vedi il SQL generato

3. **Esegui SQL direttamente (per debug)**:
   ```sql
   -- Accedi al DB Odoo
   psql -d odoo_db
   
   -- Copia il SQL generato e esegui
   SELECT DISTINCT partner_id 
   FROM account_move 
   GROUP BY partner_id 
   HAVING COUNT(*) >= 10;
   ```

4. **Verifica i risultati**:
   - Se SQL ritorna ID: ✓ Fallback ha funzionato
   - Se SQL è vuoto: ⚠️ LLM ha generato query sbagliata
   - Se SQL ha errore: ❌ Validation ha fallito

## Test Domain-based Queries

Esempi di query che dovrebbero funzionare col dominio:

### res.partner
- "Clienti"
- "Fornitori attivi"
- "Partner da Milano"

### account.move
- "Fatture non pagate"
- "Fatture di gennaio 2025"

### product.template (for prices/costs)
- "Prodotti sotto 100 euro"
- "Articoli con prezzo inferiore a 50"
- "Prodotti attivi"

### product.product (for variants)
- "Varianti con barcode"
- "Varianti attive"

## Errore: "Field X is computed and cannot be used in queries"

La LLM ha usato un campo **computed** (calcolato) come `lst_price` al posto del campo reale `list_price`.

### Root Cause:
- Il prompt della LLM non mostrava SOLO i campi stored
- La LLM ha indovinato il nome del campo

### Soluzioni Implementate (v2):
1. **Filtro dei campi**: Ora il prompt mostra SOLO i campi del database (stored)
2. **Mappature esplicite**: Per product.product, il prompt dice chiaramente:
   ```
   "price" or "selling price" = list_price
   "cost" = standard_price
   "quantity" = qty_available
   ```
3. **Messaggi di errore migliorati**: Se la LLM usa un campo sbagliato, vedrai:
   ```
   Field "lst_price" is computed (not in database).
   Use one of: active, barcode, can_image_1024_be_zoomed, ...
   ```

### Se Continua a Non Funzionare:
1. **Ricarica il modulo Odoo**: Qualche volta il cache del prompt non si aggiorna
   ```
   Odoo → Moduli App → Ovunque → Click (reload)
   ```

2. **Verifica i campi disponibili**:
   ```bash
   ./odoo-bin shell
   exec(open('/path/to/addons/ovunque/debug_fields.py').read())
   ```

3. **Usa una query più specifica**:
   - ✓ "Prodotti con list_price sotto 100"
   - ✗ "Articoli sotto i 100€" (troppo vago, LLM potrebbe confondersi)

## Altre Cause Residue

1. **Query troppo ambigua**
   - Es: "Cose" senza specificare il tipo
   - Soluzione: Usare termini più specifici

2. **API Key scaduta/invalida**
   - Soluzione: Testare con API key nuova

3. **Modello non supportato**
   - Soluzione: Aggiungere il modello a `AVAILABLE_MODELS` e a `_get_model_examples()`

## Logs da Controllare
In caso di problema persistente:
```
tail -f /var/log/odoo/odoo.log | grep "[LLM]\|[PARSE]\|[REPAIR]"
```

Questo mostrerà:
- Esatta query inviata
- Risposta ricevuta
- Tentativo di parsing
- Errori specifici
