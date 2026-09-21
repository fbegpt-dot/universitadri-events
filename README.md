# universitadri-events

Pagina essenziale per seguire i prossimi Open Day e gli appuntamenti di orientamento universitario **a Roma**.

## Ambito
Il monitor riguarda solo:
- Economia & Management
- Design
- Architettura
- Design del Gioiello

Sono escluse Cucina, Sport e Ingegneria, e sono escluse le sedi fuori Roma.

## Come funziona
Ogni lunedì mattina GitHub Actions controlla le fonti ufficiali elencate in `sources.json`, mantiene solo gli eventi futuri e aggiorna `data/events.json`.

La pagina `index.html` legge quel file e presenta gli appuntamenti in ordine cronologico.

## Affidabilità
La pagina mostra sempre il link alla fonte ufficiale. Il crawler usa criteri prudenti: un evento deve avere una data esplicita e parole riconducibili a Open Day/orientamento. Gli eventi già verificati vengono mantenuti fino alla loro data.
