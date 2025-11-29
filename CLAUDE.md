# Miglioramenti Domain Generation - Debug Guide

## ULTIMO UPDATE (v3)
L'interfaccia è stata redesignata per essere **user-friendly**:
- ✅ Seleziona categoria (Clienti, Prodotti, Ordini, ecc.)
- ✅ Il modello Odoo viene auto-selezionato dal backend
- ✅ Scrivi la query in linguaggio naturale

## Problema Originale (Risolto)
Le query spesso ritornano dominio vuoto `[]` perché la LLM non generava risposte valide.

## Soluzioni Implementate

### 1. **Prompt Migliorato** (search_query.py:111-148)
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

## Test
Esempi di query che dovrebbero funzionare ora:

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
