# Harvesting OJS/OMP Journals and Books


## Ziel

Regelmäßige automatische Veröffentlichung der Publikationen aus OJS/OMP im DSpace Repositorium.
DOI Anmeldung durch DSpace und Eintragung der DOI ins OJS/OMP.


## Export/Import SAF, DOI Eintrag im Journal 

Im ersten Schritt ruft das Python Script _journal2saf.py_ von einem [OMP](https://pkp.sfu.ca/omp) bzw. [OJS](https://pkp.sfu.ca/ojs/) Server alle relevanten Daten von **publizierten** Journalen/Monographien über das  [REST-API](https://docs.pkp.sfu.ca/dev/api/ojs/3.3) ab. 

Aus den Daten werden DSpace importierbare [SAF Archive](https://wiki.lyrasis.org/display/DSDOC5x/Importing+and+Exporting+Items+via+Simple+Archive+Format) erzeugt und im konfigurierten export Ordner abgelegt.

Im zweiten Schritt werden alle erzeugten SAF Archive automatisch über _scp_ auf den Zielserver DSpace, in ein vereinbartes Verzeichnis (Austauschordner) kopiert. 

Im Projekt befindet sich außerdem ein bash Script, mit dessen Hilfe ein unabhängiger automatischer Import der SAF's und ein Export der vergebenen [DOI's](https://www.doi.org/)  auf dem DSpace Server angestoßen wird.

<pre>
 ./dspace/bin/journals_import.sh
</pre>

Verzeichnisstruktur auf dem DSpace:
<pre>
~/&lt;austauschordner>/source
~/&lt;austauschordner>/doi
~/&lt;austauschordner>/map
</pre>


Bei jedem Kopieren neuer SAF Archive überprüft _journal2saf.py_, ob DOI Daten von bereits importierten SAF's erstellt worden sind und kopiert diese in das export Verzeichnis auf dem Publikations Server.  

&#9755; Jeder Ressource (_Fahne_) eines Journals, kann eine externe URL ([urlRemote](https://docs.pkp.sfu.ca/dev/api/ojs/3.1#tag/Submissions/paths/~1submissions~1{submissionId}/get)) zugewiesen werden.


In einem dritten Schritt hinterlegt _journal2saf.py_ die DOI's im OJS/OMP als *urlRemote* Attribut für jede Veröffentlichung.
Hierfür muss das OJS/OMP Plugin SetRemoteUrlPlugin installiert sein. 

## Setup

Python >= 3.6 ist notwendig.
Dieses Projekt clonen und in das Verzeichnis wechseln.

<pre>
python3 -m venv venv

# windows
venv\Scripts\activate.bat
# other 
source venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt
</pre>
Tests ausführen:
<pre>
pytest -v
</pre>

## Konfiguration
### *conf/config_meta.ini*
In der _config_meta.ini_ werden, die Metadaten, die OJS/OMP zur Verfügung stellt, für den Export in die entsprechenden XML Dateien vermerkt.
Die Daten können beliebig erweitert werden, sofern ein gültiger Wert im API Request geliefert wird.
Statische Werte müssen in Anführungstriche gesetzt werden und werden nicht ausgewertet.Beispieldateien für OMP und OJS liegen im Ordner ./_conf_.

### *conf/config.ini*
Diese Datei bitte aus der *conf/config.ini.example* durch umbennen erstellen.
Alle Werte sind in der Datei kommentiert.

## Start Export(SAF) / Import(DOI)
Das Script wird idealerweise von einem Cronjob aufgerufen.

<pre>
python journal2saf.py -c ./conf/config.ini -m ./conf/config_meta_ojs.ini
</pre>
 


## 


## License

siehe LICENSE Datei
