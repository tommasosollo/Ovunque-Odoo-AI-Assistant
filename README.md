# Ovunque - Natural Language Search for Odoo

Cercare nei tuoi dati Odoo come su Google. Scrivi in linguaggio naturale e l'AI fa il resto.

## Cosa Fa

**Ovunque** converte domande in italiano in query Odoo usando GPT-4:

```
Input:  "Fammi vedere tutti i clienti che non hanno ordinato negli ultimi 6 mesi"
Output: Ricerca automatica con visualizzazione dei risultati
```

## Installazione Veloce

### 1. Prerequisiti
- Odoo 19+
- Chiave API OpenAI
- Python 3.10+

### 2. Configurare OpenAI API

In Odoo vai a:
```
Ovunque → Configuration → API Settings
```

Aggiungi:
- **Key**: `ovunque.openai_api_key`
- **Value**: `sk-...` (la tua chiave da https://platform.openai.com/api-keys)

### 3. Usare il Modulo

1. Vai a **Ovunque → Search Queries**
2. Clicca **Create**
3. Scrivi una domanda (es: "Mostrami i clienti della Toscana")
4. Seleziona il modello (es: "Partner / Contact")
5. Clicca **Execute Search**

Vedrai:
- **Tab Results**: La lista dei record trovati
- **Tab Debug Info**: Il dominio generato e la risposta grezza di GPT-4

## Modelli Disponibili

| Modello | Descrizione |
|---------|-------------|
| `res.partner` | Contatti/Clienti/Fornitori |
| `account.move` | Fatture |
| `product.product` | Prodotti |
| `sale.order` | Ordini di vendita |
| `purchase.order` | Ordini di acquisto |
| `stock.move` | Movimenti magazzino |
| `crm.lead` | Lead CRM |
| `project.task` | Task progetto |

## Esempi di Query

### Partner/Contatti
- "Mostrami tutti i clienti della Toscana"
- "Chi mi deve pagare più di 5000 euro?"
- "Fornitori che non ho contattato da 1 anno"

### Fatture
- "Fatture non pagate di novembre"
- "Fatture >1000 euro dello scorso anno"
- "Fatture di Rossi del 2024"

### Prodotti
- "Prodotti in magazzino sotto 5 pezzi"
- "Tutti i prodotti della categoria Elettronica"
- "Articoli con prezzo tra 10 e 100 euro"

### Ordini
- "Ordini spediti della scorsa settimana"
- "Ordini in sospeso di Milano"
- "Vendite totali di Gennaio"

## Come Funziona Internamente

1. **Input Utente**: L'utente scrive una domanda
2. **Estrazione Campi**: Il modulo ottiene i campi disponibili dal modello selezionato
3. **Prompt GPT-4**: Crea un prompt che include:
   - Nome del modello
   - Lista dei campi disponibili
   - La domanda dell'utente
4. **Parsing**: Estrae il dominio Odoo dalla risposta
5. **Esecuzione**: Esegue `Model.search(domain)` sul database
6. **Visualizzazione**: Mostra i risultati in una tabella

## Architettura

```
ovunque/
├── __manifest__.py              # Metadati modulo
├── models/
│   └── search_query.py          # Model SearchQuery e SearchResult
├── controllers/
│   └── search_controller.py     # API REST
├── views/
│   ├── search_query_views.xml   # Viste dei model
│   └── menu.xml                 # Menu Odoo
├── security/
│   └── ir.model.access.csv      # Permessi
└── static/src/
    ├── js/search_bar.js         # Frontend (futuro)
    └── xml/search_template.xml  # Template (futuro)
```

## Database Schema

### search.query
| Campo | Tipo | Descrizione |
|-------|------|-------------|
| `name` | Char | La domanda dell'utente |
| `model_name` | Selection | Modello target (es: res.partner) |
| `model_domain` | Text | Dominio Odoo generato |
| `results_count` | Integer | Numero risultati trovati |
| `status` | Selection | draft / success / error |
| `error_message` | Text | Messaggio di errore (se presente) |
| `raw_response` | Text | Risposta grezza di GPT-4 |
| `result_ids` | One2many | Record dei risultati |
| `created_by_user` | Many2one | Utente che ha creato la query |

### search.result
| Campo | Tipo | Descrizione |
|-------|------|-------------|
| `query_id` | Many2one | Query che ha generato questo risultato |
| `record_id` | Integer | ID del record trovato |
| `record_name` | Char | Nome/display_name del record |
| `model` | Char | Nome del modello |

## Troubleshooting

### Errore: "Invalid domain format received from LLM"

GPT-4 non ha generato un dominio valido. Cause comuni:
- Campo non esiste nel modello
- Tipo di dato non supportato
- Query ambigua o non supportata

**Soluzione**: Controlla il "Raw LLM Response" nella tab Debug Info per vedere cosa ha generato GPT-4.

### Errore: "Could not parse the query"

Il dominio restituito da GPT-4 è vuoto `[]` o invalido.

**Soluzione**: Ripeti la query usando termini diversi o più specifici.

### Nessun risultato `(0 risultati)`

La query è stata processata correttamente, ma nessun record corrisponde. È normale.

### Errore: "OpenAI API key not configured"

Non hai impostato la chiave API.

**Soluzione**: Vai a Ovunque → Configuration → API Settings e aggiungi la chiave.

## Limitazioni

- ⚠️ **Massimo 50 risultati** per query (impostabile in code)
- ⚠️ **Supporta solo modelli standard** di Odoo
- ⚠️ **Richiede connessione a OpenAI** (API a pagamento)
- ⚠️ **Non supporta JOIN** tra modelli
- ⚠️ **Lingua**: Supporta input in italiano/inglese

## API Endpoints

### POST /ovunque/search
Ricerca main endpoint.

**Request**:
```json
{
  "query": "fatture non pagate",
  "model": "account.move"
}
```

**Response**:
```json
{
  "success": true,
  "results": [
    {"id": 1, "display_name": "INV/2025/001"},
    {"id": 2, "display_name": "INV/2025/002"}
  ],
  "count": 2,
  "domain": "[('state', '!=', 'paid')]",
  "query_id": 42
}
```

### GET /ovunque/models
Lista modelli disponibili.

**Response**:
```json
{
  "success": true,
  "models": [
    {"name": "res.partner", "label": "Partner / Contact"},
    {"name": "account.move", "label": "Invoice"}
  ]
}
```

## Permessi

Il modulo crea due accessi:
- **User**: Può creare, leggere e modificare le proprie query
- **Manager**: Accesso completo (including delete)

## License

AGPL-3.0

## Support

Per bug, suggerimenti o domande: aprire un issue nel repository.
