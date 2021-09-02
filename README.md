# Harvesting OJS/OMP Journals and Books


Das Script _journal2saf.py_ ruft von einem, im Konfigurationsfile angegebenen Journalserver, alle relevanten Daten, von bereits pulizierten Journalen/Büchern ab.


Aus diesen Daten werden [SAF Dateien](https://wiki.lyrasis.org/display/DSDOC5x/Importing+and+Exporting+Items+via+Simple+Archive+Format) erzeugt, die von einem D_Space Server regelmäßig importiert werden.

## Ziel:

Automatische Veröffentlichung der Publikationen im D-Space Repositorium.

## TODO:

Bidirektionaler Datenaustausch zwischen OJS/OMP mit dem D-Space Server.
Hat der D-Space Server die Daten importiert, sollte er einen [DOI](https://de.wikipedia.org/wiki/Digital_Object_Identifier) anfordern und ihn auf geeignete Weise an die Journalserver zurückliefern.

Der DOI soll anschließend im Journalserver via API eingetragen werden.

Das Script soll später viá cronjob regelmäßig den/die Journalserver abfragen, um aktuell Veröffentlichungen im D-Space anzuzeigen und mit einem DOI zu versehen.