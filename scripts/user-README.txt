Falcon — installazione (senza Python, uv o pip)
==============================================

1. Scompatta l’archivio Falcon-macos-*.zip o Falcon-win64.zip
2. macOS: doppio clic su Install.command (oppure esegui install-macos.sh)
   Windows: clic destro Install.ps1 → Esegui con PowerShell
3. Apri un nuovo terminale e digita:

   falcon record --name demo
   (Ctrl+C per fermare)

   falcon analyze --session demo
   falcon distill --session demo    (richiede AI_GATEWAY_API_KEY)
   falcon report --session demo     (stampa report.md: processo per fasi,
                                     criticità, opportunità, ontologia)

Permessi macOS: Accessibility (+ spesso Input Monitoring) per falcon-recorder
in Impostazioni → Privacy e sicurezza.

Configurazione opzionale: copia config.toml.example in config.toml
nella stessa cartella dell’installazione, oppure usa --config.

Supporto tecnico: falcon check --session demo
