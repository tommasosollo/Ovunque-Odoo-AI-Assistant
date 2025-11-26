# Ovunque - Natural Language Search for Odoo

Cercare nei tuoi dati Odoo come su Google. Scrivi in linguaggio naturale e l'AI fa il resto.

## Cosa Fa

**Ovunque** converte domande in italiano in query Odoo usando GPT-4:

```
Input:  "Fammi vedere tutti i clienti che non hanno ordinato negli ultimi 6 mesi"
Output: Ricerca automatica con visualizzazione dei risultati
```

## Configurazione Iniziale

### Prerequisiti
- **Odoo**: versione 19.0+
- **Python**: 3.10+
- **OpenAI API key**: da https://platform.openai.com/api-keys

### Installazione del Modulo

```bash
# 1. Copia il modulo nella directory addons di Odoo
cp -r addons/ovunque /path/to/your/odoo/addons/

# 2. Installa le dipendenze Python
pip install -r /path/to/your/odoo/addons/ovunque/requirements.txt

# 3. Riavvia Odoo
./odoo-bin -u all
```

### Configurare OpenAI API

Una volta in Odoo:

1. Vai a **Ovunque → Configuration → API Settings**
2. Crea un nuovo parametro di configurazione:
   - **Key**: `ovunque.openai_api_key`
   - **Value**: `sk-...` (la tua chiave)

Oppure via Python shell:
```python
env['ir.config_parameter'].sudo().set_param('ovunque.openai_api_key', 'sk-your-key')
```

## Struttura del Progetto

```
ai-odoo-data-assistant/
├── addons/
│   └── ovunque/                      # Modulo principale Odoo
│       ├── __manifest__.py           # Metadati modulo
│       ├── __init__.py               # Import models/controllers
│       ├── models/
│       │   ├── __init__.py
│       │   └── search_query.py      # Model SearchQuery e SearchResult
│       ├── controllers/
│       │   ├── __init__.py
│       │   └── search_controller.py # REST API endpoints
│       ├── views/
│       │   ├── search_query_views.xml# UI model e form
│       │   └── menu.xml              # Menu Odoo
│       ├── security/
│       │   └── ir.model.access.csv  # Permessi accesso
│       ├── requirements.txt          # Dipendenze Python
│       ├── utils.py                  # Funzioni utilità
│       ├── tests.py                  # Test unitari
│       ├── config_example.py         # Script configurazione
│       ├── README.md                 # Documentazione utenti
│       ├── DEVELOPMENT.md            # Guida sviluppatori
│       ├── QUICKSTART.md             # Guida veloce
│       ├── .env.example              # Template variabili ambiente
│       └── .gitignore                # Esclusioni Git
└── README.md                         # Questo file
```

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

1. **Input Utente**: L'utente scrive una domanda in linguaggio naturale
2. **Estrazione Campi**: Il modulo recupera i campi disponibili dal modello selezionato
3. **Prompt GPT-4**: Crea un prompt specializzato che include:
   - Nome e descrizione del modello
   - Lista completa dei campi disponibili con tipi
   - La domanda dell'utente in italiano
   - Vincoli e operatori supportati
4. **Parsing**: Estrae il dominio Odoo dalla risposta di GPT-4
5. **Esecuzione**: Esegue `Model.search(domain)` sul database
6. **Visualizzazione**: Mostra i risultati in una tabella interattiva

## API Endpoints

### POST /ovunque/search
Endpoint principale per le ricerche.

**Request**:
```json
{
  "jsonrpc": "2.0",
  "method": "call",
  "params": {
    "query": "fatture non pagate",
    "model": "account.move"
  }
}
```

**Response**:
```json
{
  "jsonrpc": "2.0",
  "result": {
    "success": true,
    "results": [
      {"id": 1, "display_name": "INV/2025/001"},
      {"id": 2, "display_name": "INV/2025/002"}
    ],
    "count": 2,
    "domain": "[('state', '!=', 'paid')]",
    "query_id": 42
  }
}
```

### GET /ovunque/models
Recupera lista di modelli disponibili.

**Response**:
```json
{
  "jsonrpc": "2.0",
  "result": {
    "success": true,
    "models": [
      {"name": "res.partner", "label": "Partner / Contact"},
      {"name": "account.move", "label": "Fatture"},
      {"name": "product.product", "label": "Prodotti"}
    ]
  }
}
```

## Database Schema

### search.query
| Campo | Tipo | Descrizione |
|-------|------|-------------|
| `name` | Char | La domanda dell'utente |
| `model_name` | Selection | Modello target (es: res.partner) |
| `model_domain` | Text | Dominio Odoo generato da GPT-4 |
| `raw_response` | Text | Risposta grezza di GPT-4 |
| `results_count` | Integer | Numero risultati trovati |
| `status` | Selection | draft / success / error |
| `error_message` | Text | Messaggio di errore (se presente) |
| `result_ids` | One2many | Record dei risultati (One2many su search.result) |
| `created_by_user` | Many2one | Utente che ha creato la query |

### search.result
| Campo | Tipo | Descrizione |
|-------|------|-------------|
| `query_id` | Many2one | Query che ha generato questo risultato |
| `record_id` | Integer | ID del record trovato nel modello target |
| `record_name` | Char | Nome/display_name del record |
| `model` | Char | Nome del modello (es: res.partner) |

## Permessi

Il modulo implementa due livelli di accesso (vedi `security/ir.model.access.csv`):

- **User**: Può creare, leggere e modificare query; può leggere risultati
- **Manager**: Accesso completo incluso delete

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

**Soluzione**: Vai a Ovunque → Configuration → API Settings e aggiungi la chiave, oppure usa il file `.env`.

## Limitazioni

- ⚠️ **Massimo 50 risultati** per query (impostabile in code)
- ⚠️ **Supporta solo modelli standard** di Odoo
- ⚠️ **Richiede connessione a OpenAI** (API a pagamento)
- ⚠️ **Non supporta JOIN** tra modelli
- ⚠️ **Lingua**: Supporta input in italiano/inglese (estendibile ad altre lingue)


## Sviluppo

Leggi [DEVELOPMENT.md](addons/ovunque/DEVELOPMENT.md) per:
- Setup ambiente di sviluppo
- Struttura dettagliata del codice
- Come debuggare e testare
- Come estendere il modulo con nuovi modelli
- Come integrare altri LLM (Claude, Ollama, ecc.)

## License

AGPL-3.0
