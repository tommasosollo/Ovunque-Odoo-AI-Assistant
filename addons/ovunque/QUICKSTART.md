# Quick Start Guide - Ovunque

## 5 minuti per iniziare

### 1. Installa il modulo

```bash
# Copia il modulo in addons/
cp -r ovunque /path/to/odoo/addons/

# Oppure clona da git
git clone <repo> /path/to/odoo/addons/ovunque
```

### 2. Installa dipendenze Python

```bash
pip install -r ovunque/requirements.txt
```

### 3. Riavvia Odoo

```bash
./odoo-bin -c config.conf -u all
```

### 4. Installa il modulo da Odoo

1. **App** → **App Library**
2. Cerca **Ovunque**
3. Clicca **Install**

### 5. Configura OpenAI API Key

Opzione A - Via Odoo UI:
1. **Ovunque** → **Configuration** → **API Settings**
2. Crea parametro con Key: `ovunque.openai_api_key` e Value: `sk-...`

Opzione B - Via Python:
```python
env['ir.config_parameter'].sudo().set_param('ovunque.openai_api_key', 'sk-your-key')
```

Opzione C - Via variabile d'ambiente:
```bash
export OPENAI_API_KEY=sk-your-key
```


## Troubleshooting

### Errore: "API key not configured"

Soluzione: Imposta la API key seguendo il passo 5

### Errore: "Could not parse the query"

Motivi:
- Query troppo complessa
- Nome del campo non riconosciuto
- LLM ha fatto un errore

Soluzione: Prova con una query più semplice o controlla i logs in **Ovunque** → **Search Queries**

### Modulo non appare in App Library

Soluzione:
1. Vai a **Settings** → **Technical** → **Modules** → **Update Modules List**
2. Cerca "ovunque" e installa

### "ModuleNotFoundError: No module named 'openai'"

Soluzione:
```bash
pip install openai>=1.0.0
```

## Prossimi Passi

Leggi [README.md](README.md) per:
- Architettura dettagliata
- Configurazione avanzata
- Come estendere il modulo
- Come creare custom LLM integrations
