# Harvesting OJS/OMP Journals and Books


Das Python Script _journal2saf.py_ ruft von einem [OMP](https://pkp.sfu.ca/omp) bzw. [OJS](https://pkp.sfu.ca/ojs/) Server alle relevanten Daten von **publizierten** Journalen/Monographien über das  [REST-API](https://docs.pkp.sfu.ca/dev/api/ojs/3.3) ab.
Haben die Fahnen eine externe URL (urlRemote), werden sie ignoriert!

Aus den Daten werden DSpace lesbare [SAF Archive](https://wiki.lyrasis.org/display/DSDOC5x/Importing+and+Exporting+Items+via+Simple+Archive+Format) erzeugt.

Im Projekt befindet sich außerdem ein bash Script, mit dessen Hilfe ein unabhängiger automatischer Import der SAF's und ein Export der vergebenen [DOI's](https://www.doi.org/) angestoßen wird.

Bei jedem Export neuer SAF Archive überprüft _journal2saf.py_, ob DOI Daten von bereits importierten SAF's erstellt worden sind und kopiert diese in das export Verzeichnis.

Die DOI's hinterlegt _journal2saf.py_ im OJS/OMP als *urlRemote* Attribut für jede Veröffentlichung.

## Ziel

Regelmäßige automatische Veröffentlichung der Publikationen aus OJS/OMP im DSpace Repositorium.
DOI Anmeldung durch DSpace und Übermittlung der DOI ins OJS/OMP.

## Setup

Python >= 3.6 ist notwendig.
Dieses Project clonen und in das Verzeichnis wechseln.

```
python3 -m venv venv

# windows
venv\Scripts\activate.bat
# other 
source venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt
```
Tests ausführen:
```
pytest -v
```

## Konfiguration
### *conf/config_meta.ini*
In der _config_meta.ini_ werden die Daten, die OJS/OMP zu Verfügung stellt, in entsprechende XML Dateien gespeichert.
Die Daten können beliebig erweitert werden, sofern ein gültiger Wert im API Request geliefert wird.
Statische Werte müssen in Anführungstriche gesetzt werden.

### *conf/config.ini*
Diese Datei bitte aus der *conf/config.ini.example* durch umbennen erstellen.
Alle Werte sind in der Datei kommentiert.

## Start Export(SAF) / Import(DOI)
Das Script wird idealerweise von einem Cronjob aufgerufen.

```
python journal2saf.py -c ./conf/config.ini
```

## 


## License

siehe LICENSE Datei