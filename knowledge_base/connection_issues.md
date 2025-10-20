# Problemi di Connessione Internet

**PREREQUISITO**: Cliente già identificato con verify_customer()

## Diagnostica Generale

Quando un cliente segnala problemi di connessione, la priorità è capire se il problema è:
- Assenza totale di connessione
- Connessione intermittente
- Problema solo WiFi o anche cablata

## Verifica Iniziale

### Controllo Modem
Il primo passo è sempre verificare lo stato del modem:
- **Luci accese?** Se il modem è spento, è un problema di alimentazione
- **Luce Power**: deve essere fissa verde
- **Luce Internet/DSL**: deve essere fissa verde (se rossa o lampeggiante = problema linea)
- **Luce WiFi**: deve essere accesa se si usa il WiFi

### Stati delle Luci e Significato

**Tutte le luci spente:**
- Modem non alimentato
- Problema alla presa elettrica
- Alimentatore danneggiato
→ Far controllare alimentazione e prese

**Solo Power accesa:**
- Problema sulla linea telefonica
- Cavo DSL/fibra scollegato o danneggiato
→ Controllare cavi, poi verificare linea con tool check_line_status()

**Power + Internet lampeggianti:**
- Modem in fase di sincronizzazione
- Normale durante l'avvio (2-3 minuti)
- Se persiste oltre 5 minuti = problema linea
→ Attendere, poi usare tool di check linea

**Internet rossa fissa:**
- Problema autenticazione
- Possibile guasto sulla linea
- Modem non sincronizza
→ Usare tool check_line_status()

## Diagnostica Cablata vs WiFi

È fondamentale capire se il problema è generalizzato o solo WiFi:

**Test da fare:**
"Ha la possibilità di collegare un dispositivo con cavo ethernet direttamente al modem?"

**Se funziona via cavo ma non WiFi:**
- Il problema è la rete wireless, non la connessione internet
→ Vedere documentazione problemi WiFi

**Se non funziona neanche via cavo:**
- Problema sulla linea internet o configurazione modem
→ Usare check_line_status() per diagnostica

## Uso dei Tools

### check_line_status(customer_id)
Usare questo tool quando:
- Le luci indicano problema linea (internet rossa/lampeggiante)
- Non funziona né via WiFi né via cavo
- Cliente segnala "internet completamente assente"

Il tool restituisce:
- line_status: "active" | "down" | "degraded"
- signal_quality: 0-100%
- downstream_speed: Mbps effettivi
- upstream_speed: Mbps effettivi
- connection_drops_24h: numero disconnessioni ultime 24h
- last_sync: timestamp ultima sincronizzazione

### reset_modem(customer_id)
Usare questo tool quando:
- La linea risulta attiva ma il modem non sincronizza
- Dopo verifiche fisiche (cavi ok, luci ok)
- Come tentativo di risoluzione dopo check fallito

**IMPORTANTE**: Avvisare sempre il cliente che il modem si riavvierà e la connessione cadrà per 2-3 minuti.

### run_speed_test(customer_id)
Usare quando:
- Cliente lamenta lentezza ma connessione presente
- Dopo risoluzione di un problema, per verificare ripristino
- Per confrontare velocità reale vs contrattuale

## Pattern Comuni e Soluzioni

### Problema dopo temporale
- Spesso danneggiamento filtri ADSL
- Possibile problema centralina
→ Check linea, se down aprire ticket tecnico

### Problema dopo lavori in casa
- Spesso cavo scollegato o danneggiato
→ Far controllare tutti i cavi prima di diagnostica remota

### Problema intermittente
- Controllare statistiche drop e qualità segnale
→ check_line_status() e analizzare connection_drops_24h
→ Se >10 drop in 24h = problema linea da escalare

## Escalation a Tecnico

Escalare quando:
- line_status = "down" persistente dopo reset
- signal_quality < 50% persistente
- connection_drops_24h > 10
- Cliente segnala danni fisici alla linea
- Problema non risolto dopo 15 minuti di troubleshooting
