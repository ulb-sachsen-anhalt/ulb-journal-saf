# Harvesting OJS/OMP Journals and Books


Das Python Script _journal2saf.py_ ruft von einem [OMP](https://pkp.sfu.ca/omp) bzw. [OJS](https://pkp.sfu.ca/ojs/) Server alle relevanten Daten von pulizierten Journalen/Monographien über das REST-API ab.

Aus den Daten werden DSpace lesbare [SAF Archive](https://wiki.lyrasis.org/display/DSDOC5x/Importing+and+Exporting+Items+via+Simple+Archive+Format) erzeugt.

Im Projekt befindet außerdem sich ein bash Script, mit dessen Hilfe ein unabhängiger automatischer Import der SAF's und ein Export der vergebenen [DOI's](https://www.doi.org/) angestoßen wird.

Bei jedem Export neuer SAF Archive überprüft _journal2saf.py_, ob DOI Daten von bereits importierten SAF's erstellt worden sind.

Die DOI's hinterlegt _journal2saf.py_ im OJS/OMP als *urlRemote* Attribut für jede Veröffentlichung.

## Ziel:

Regelmäßige automatische Veröffentlichung der Publikationen aus OJS/OMP im DSpace Repositorium.
DOI Anmeldung durch DSpace und Übermittlung der DOI ins OJS/OMP.

