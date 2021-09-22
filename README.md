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

Um das Dantenbankfeld pub-id::doi anzulegen, ist es notwendig das DOI Plugin zu aktivieren!

Hier eine Bspl. Request (PUT) um die DOI umzuschreiben:

curl -k -X PUT -H "Content-Type: application/json" -d '{"urlRemote":"path to dspace/handle"}' https://publicdev.bibliothek.uni-halle.de/hdwiso/api/v1/submissions/101?apiToken=xyz-usw...


Resultat:
https://publicdev.bibliothek.uni-halle.de/hdwiso/api/v1/submissions/101


hier gibt es 2 files / checken wie das Programm reagiert
https://publicdev.bibliothek.uni-halle.de/cicadina/api/v1/submissions

Leider kann man die remoteUrl nicht ändern, was ein Problem ist:
curl -k -X PUT -H "Content-Type: application/json" -d '{"urlRemote":"test"}' https://publicdev.bibliothek.uni-halle.de/hdwiso/api/v1/submissions/101/publications/100?apiToken=\<token\>
{"error":"api.publication.403.cantEditPublished","errorMessage":"Sie k\u00f6nnen diesen Beitrag nicht \u00e4ndern, denn er wurde bereits ver\u00f6ffentlicht."}(venv) amuyf@ULB-201007Z:~/ulb-it-migration$


docker exec --user dspace dspace-test_dspace_1 /opt/dspace/repo/bin/dspace import --help

Wenn nicht veröffentlicht geht curl -k -X PUT -H “Content-Type: application/json” -d '{“authorsString”:”http://test.de”}' https://publicdev.bibliothek.uni-halle.de/test/api/v1/submissions/2429/publications/2367?apiToken=e....


Folgendes geht (getestet):

curl -k -X PUT -H "Content-Type: application/json" -d '{"urlPath":"test"}' https://publicdev.bibliothek.uni-halle.de/hdwiso/api/v1/submissions/101/publications/100?apiToken=
hier einzusehen:
https://publicdev.bibliothek.uni-halle.de/hdwiso/workflow/index/101/5#publication/issue


geht auch:
curl -k -X PUT -H "Content-Type: application/json" -d '{"type":{"de_DE":"test"}}' https://publicdev.bibliothek.uni-halle.de/hdwiso/api/v1/submissions/101/publications/100?apiToken=

Wir müssen wohl ein PlugIn schreiben um die  *urlPublished* zu modifizieren nach einem Dspace export