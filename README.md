# AI Data Assistant (Odoo module)

Compatibilità: Odoo 16, Odoo 17

## Installazione
1. Copia la cartella `odoo_ai_data_assistant` in `addons` del tuo server Odoo.
2. Riavvia Odoo server.
3. Attiva la modalità sviluppatore e aggiorna la lista dei moduli.
4. Installa il modulo `AI Data Assistant`.

## Configurazione LLM
- Vai in Impostazioni > Parametri di Sistema > Parametri
- Aggiungi/Modifica i seguenti parametri:
  - `ai_data_assistant.endpoint` → l'endpoint HTTP del tuo provider LLM (es: Claude/OpenAI HTTP endpoint or proxy)
  - `ai_data_assistant.api_key` → chiave API
  - `ai_data_assistant.model` → nome del modello (es. gpt-4o)

Nota: l'endpoint deve accettare POST JSON con chiavi `model` e `input` (adattare `models/llm_client.py` per provider con payload differente).

## Uso
- Quando crei o modifichi contatti/prodotti/ordini, il modulo invierà un prompt al LLM per suggerimenti di dedup/normalizzazione.
- Se il LLM suggerisce modifiche ad alto confidence, verrà mostrato un wizard per confermare applicazione.
- Vai su **AI Data Assistant > Query NL** per inserire una query in linguaggio naturale (es. "Mostrami i clienti che hanno fatto almeno 3 ordini negli ultimi 6 mesi").

## Testing
- I test si trovano in `tests/test_ai_assistant.py`.
- Esegui `--test-enable` oppure usa il comando Odoo test runner.

## Prompt di esempio
- Inserimento: vedi i prompt in `models/ai_assistant.py`.
- NL->ORM: "Mostrami i clienti che hanno fatto almeno 3 ordini negli ultimi 6 mesi".

## Limitazioni & Note
- Questo modulo fornisce un wrapper generico LLM; potresti dover adattare l'`llm_client` al vendor (Claude, OpenAI o un LLM on-premise).
- Le azioni automatiche di merge sono volutamente conservative: richiedono conferma.
- Evita di memorizzare la API key nei log. Il modulo legge la key da `ir.config_parameter`.

## Suggerimenti di deploy
- Per ambienti di produzione, usa un proxy per il provider LLM e limita il traffico.
- Configura i permessi gruppo `AI Data Assistant / Manager` per operazioni di merge automatiche.

