# Problemi WiFi

**PREREQUISITO**: Cliente già identificato e connessione internet funzionante via cavo

## Quando Diagnosticare come Problema WiFi

Se il cliente può navigare via cavo ethernet ma non via WiFi, il problema è la rete wireless, non la linea internet.

## Scenari WiFi Comuni

### WiFi Non Visibile

**Sintomo:** Il cliente non vede la rete WiFi del modem tra quelle disponibili

**Diagnosi:**
1. Verificare che il pulsante/LED WiFi sul modem sia acceso
2. Il WiFi potrebbe essere stato disabilitato accidentalmente
3. Il modem potrebbe essere in modalità solo cavo

**Soluzione:**
"Controlli se sul modem c'è un pulsante con il simbolo WiFi. Se il LED WiFi è spento, prema il pulsante per attivarlo. Attendere 30 secondi e verificare se la rete appare."

### Password WiFi Errata

**Sintomo:** Il cliente vede la rete ma non riesce a connettersi, errore password

**Soluzione:**
"La password WiFi si trova sull'etichetta sotto il modem. Spesso è una combinazione di lettere maiuscole e numeri. Faccia attenzione a maiuscole/minuscole e a non confondere:
- Zero (0) con lettera O
- Uno (1) con lettera I o L
Provi a inserirla carattere per carattere guardando l'etichetta."

**Alternative:**
- Se il cliente ha smarrito l'etichetta, può usare il tool change_wifi_password() per impostarne una nuova
- Se il modem ha WPS, può suggerire la connessione tramite pulsante WPS

### Segnale Debole

**Sintomo:** Connesso ma segnale debole, frequenti disconnessioni, lentezza

**Domande diagnostiche:**
- "A che distanza è il dispositivo dal modem?"
- "Quante pareti ci sono tra il dispositivo e il modem?"
- "È in un piano diverso rispetto al modem?"

**Cause comuni:**
- Troppa distanza
- Pareti spesse/cemento armato
- Interferenze da altri dispositivi

**Soluzioni:**
1. Avvicinare il dispositivo al modem per test
2. Verificare se migliora in una stanza diversa
3. Controllare se ci sono elettrodomestici vicini al modem (microonde, cordless)

**Tool da usare:**
```
change_wifi_channel(customer_id, channel)
```
Se ci sono molte reti WiFi vicine (condomini), cambiare canale può ridurre interferenze.
Canali consigliati 2.4GHz: 1, 6, 11 (non si sovrappongono)

### Dispositivi Non Si Connettono

**Sintomo:** Il WiFi funziona su alcuni dispositivi ma non su altri

**Cause possibili:**
- Numero massimo dispositivi raggiunto (tipicamente 32-64 per modem consumer)
- Dispositivo vecchio non compatibile con standard moderni
- MAC filtering attivo

**Soluzione:**
"Provi a disconnettere alcuni dispositivi non in uso dal WiFi e riprovi. I modem hanno un limite di dispositivi collegabili contemporaneamente."

Per dispositivi vecchi:
"Il suo dispositivo potrebbe non essere compatibile con gli standard WiFi più recenti. Verifichi se nelle impostazioni WiFi può selezionare la rete a 2.4GHz invece che 5GHz. La rete 2.4GHz è più compatibile."

### WiFi 2.4GHz vs 5GHz

**Differenze da spiegare:**

**2.4GHz:**
- Più compatibile (dispositivi vecchi)
- Maggior copertura
- Attraversa meglio le pareti
- Più interferenze possibili
- Velocità minore

**5GHz:**
- Velocità superiore
- Meno interferenze
- Portata minore
- Non attraversa bene le pareti
- Serve dispositivo compatibile

**Consiglio:**
"Per dispositivi lontani o vecchi usi la rete 2.4GHz. Per streaming video, gaming o dispositivi moderni vicini al modem usi la 5GHz."

## Tools Disponibili

### change_wifi_password(customer_id, new_password)
Quando usare:
- Cliente ha dimenticato la password
- Vuole password personalizzata più facile da ricordare
- Password di default compromessa

### change_wifi_channel(customer_id, channel)
Quando usare:
- Segnale debole in zone con molte reti WiFi
- Interferenze frequenti
- Dopo verificato che il problema è interferenza e non distanza

Canali consigliati:
- 2.4GHz: 1, 6, 11
- 5GHz: auto (meno affollato)

## Escalation

Escalare quando:
- Problema persiste dopo tutte le verifiche base
- Sospetto guasto hardware WiFi del modem
- Cliente richiede configurazioni avanzate (bridge mode, port forwarding, etc.)
- Cliente in business necessita estensori WiFi professionali
