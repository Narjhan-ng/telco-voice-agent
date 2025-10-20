# Problemi di Velocità

**PREREQUISITO**: Cliente identificato e connessione presente (ma lenta)

## Diagnostica Velocità Lenta

### Prima Azione: Speed Test
Usa immediatamente:
```
run_speed_test(customer_id)
```

Questo ti darà:
- download_speed: Mbps in download
- upload_speed: Mbps in upload
- latency: millisecondi
- jitter: variazione latency

### Interpretazione Risultati

**Confronta con velocità contrattuale del cliente**
(Disponibile da verify_customer - contract_speed)

**Se velocità è 80-100% del contrattuale:**
"Il test mostra [X] Mbps, in linea con i [Y] Mbps del suo contratto. La velocità è corretta. La lentezza potrebbe dipendere da:
- Troppi dispositivi connessi contemporaneamente
- Sito/servizio specifico sovraccarico
- Dispositivo del cliente datato"

**Se velocità è 50-80% del contrattuale:**
"Rilevo [X] Mbps contro [Y] attesi. C'è una riduzione ma nella norma per ADSL/FTTC. Possibili cause:
- Distanza dalla centrale (per ADSL)
- Ora di punta
- Qualità linea degradata"
→ Controlla signal_quality con check_line_status()

**Se velocità è <50% del contrattuale:**
"La velocità è molto ridotta. Verifico la qualità della linea..."
→ check_line_status() per analisi approfondita

## Fattori che Influenzano Velocità

### Troppi Dispositivi Connessi

**Domanda diagnostica:**
"Quanti dispositivi sono connessi in questo momento alla rete? TV, smartphone, tablet, console..."

**Spiegazione al cliente:**
"La banda viene divisa tra tutti i dispositivi. Se qualcuno sta facendo download, streaming 4K, o aggiornamenti, può rallentare gli altri dispositivi."

**Soluzione:**
"Provi a disconnettere i dispositivi non in uso e verifichi se migliora."

### WiFi vs Cavo

**Sempre chiedere:**
"Sta usando WiFi o cavo ethernet?"

**Se WiFi:**
"Il WiFi è più comodo ma può essere più lento del cavo, specialmente se è lontano dal modem. Per il test più accurato, se possibile si colleghi con cavo."

**Tool da usare:**
Se via cavo la velocità è ok ma via WiFi è bassa → problema WiFi
→ Vedi documentazione wifi_issues.md

### Server di Test

"La velocità può variare in base al sito che sta usando. Alcuni server sono più lenti di altri. Per avere una misura accurata, le ho fatto io un test diretto sulla sua linea."

## Problemi Tecnici Linea

### Degradazione Segnale

Usa check_line_status() per vedere signal_quality:

**signal_quality 80-100%:** Linea ottima
**signal_quality 60-80%:** Linea accettabile, può influire su velocità
**signal_quality <60%:** Linea degradata, problema tecnico

**Se signal_quality bassa:**
"Rilevo un problema di qualità sulla linea che sta riducendo la velocità. Questo può dipendere da:
- Cavi deteriorati
- Filtri ADSL malfunzionanti (solo per ADSL)
- Problema sulla tratta dalla centrale"

**Azione:**
Prova reset_modem() - a volte risincronizza meglio
Se non migliora → escalation tecnica

### Attenuazione Linea (ADSL/FTTC)

Per contratti ADSL/FTTC, la velocità dipende dalla distanza dalla centrale.

**Spiegazione al cliente:**
"La tecnologia ADSL/FTTC ha velocità che diminuiscono con la distanza dalla centrale telefonica. Se la sua abitazione è distante, la velocità massima raggiungibile può essere inferiore a quella pubblicizzata."

**Se velocità è < 30% contrattuale:**
Verifica contratto - potrebbe essere candidato per upgrade a fibra FTTH
→ Segnala a commerciale

## Speed Test Interpretazione Avanzata

### Latency (Ping)

**<20ms:** Ottima - perfetto per gaming
**20-50ms:** Buona - ok per uso normale
**50-100ms:** Accettabile - può dare problemi in gaming
**>100ms:** Alta - problemi in applicazioni real-time

**Se latency alta:**
Possibile:
- Linea congestionata
- Problema routing
- WiFi con interferenze
→ Test via cavo, poi check_line_status()

### Jitter

**<10ms:** Ottimo
**10-30ms:** Accettabile
**>30ms:** Problematico per VoIP/gaming

Jitter alto indica instabilità linea
→ check_line_status() per vedere connection_drops

## Casi Specifici

### Lento Solo in Certe Ore

"Se la lentezza è solo in certi orari (sera 20-23), può essere congestione di rete nelle ore di punta. È un fenomeno comune quando molti utenti della zona usano internet contemporaneamente."

Verifica pattern con cliente, se confermato:
→ Segnalazione a supporto tecnico per analisi congestione

### Lento Solo su Certi Siti/Servizi

"Se la lentezza è solo su alcuni siti (es. Netflix, YouTube), il problema potrebbe essere:
- Server del servizio sovraccarico
- Peering tra provider
- Throttling (raro in Italia)"

Test con speed test neutrale
→ Se speed test ok ma servizio lento = problema del servizio, non della linea

### Download OK, Upload Lento (o Viceversa)

Normale per contratti asimmetrici (es. 100/20 Mbps)

"Il suo contratto prevede [X] Mbps in download e [Y] in upload. L'upload è normalmente più basso. È nella norma."

Se upload molto più basso del previsto:
→ check_line_status() per verificare qualità upstream

## Tools Summary

```python
run_speed_test(customer_id)  # Sempre come primo step
check_line_status(customer_id)  # Se velocità molto bassa o latency alta
reset_modem(customer_id)  # Se signal_quality degradata
```

## Escalation

Escalare quando:
- Velocità <30% contrattuale persistente
- signal_quality <50% anche dopo reset
- Problema solo in upload/download (asimmetria anomala)
- Cliente business con SLA
- Sospetto throttling o problema peering
