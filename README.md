# Harvesting of datasets from the ULB Sachsen-Anhalt's OJS/OMP installations to a DSpace based Repository


## General Goals 

Automatic publication of contents of OJS and OMP contents (journals, series, monographs) in a DSpace 6.3. Repository.
DOI registration of exported contents via the DSpace repository.
Return and adequate storage of the DOI metadata information into the OJS and OMP systems.



## 1. Metadata retrieval in OJS/OMP

In this first step the Python Script _journal2saf.py_ is used to get all relevant metadata for the contributions in a given [OMP](https://pkp.sfu.ca/omp) or [OJS](https://pkp.sfu.ca/ojs/) server which are marked already as **published** and that are to be sent to DSpace. This is done via the [REST-API](https://docs.pkp.sfu.ca/dev/api/ojs/3.3). 
 
## 2. Creation of SAF-Data Packages for the import and copying to DSpace

This same script then converts the extracted data from OJS/OMP into the [SAF Archive](https://wiki.lyrasis.org/display/DSDOC5x/Importing+and+Exporting+Items+via+Simple+Archive+Format) format which is used by DSpace installations to import data into a standard DSpace collection. These data are saved in a previously defined export folder. 

Once in this folder, newly created SAF-Archive files are then copied using _scp_ to the target DSpace installation in a previously defined folder. 

A bash script is then used to automatically import SAF files and also to export a list of all newly created [DOI's](https://www.doi.org/) by the DSpace installation which processes the new data files. This bash script is triggered in the DSpace server. 

<pre>
 ./dspace/bin/journals_import.sh
</pre>

The following directory structure in DSpace is used:
<pre>
~/&lt;austauschordner>/source
~/&lt;austauschordner>/doi
~/&lt;austauschordner>/map
</pre>

## 3. DOI Information checks in DSpace and storage in the metadaten schema of OJS/OMP
Everytime new SAF files are copied into DSpace, the script _journal2saf.py_ checks if DOIs from SAF files which have been already imported are available in which case these get copied to the corresponding export folder in DSpace.

### 

&#9755; For each ressource ((_a galley_ or _publicationFormat_) in OJS/OMP terminology) in a journal an external URL can be stored in the field ([urlRemote](https://docs.pkp.sfu.ca/dev/api/ojs/3.1#tag/Submissions/paths/~1submissions~1{submissionId}/get))


The script _journal2saf.py_ ensures that the newly available DOIs are stored in OJS/OMP as *urlRemote* attribute for each publication. For this to work properly, the OJS/OMP Plugin [SetRemoteUrlPlugin](https://github.com/ulb-sachsen-anhalt/setRemoteUrlPlugin) must be previously installed.


## Setup

Make sure you use Python 3.6 or higher. Clone the project and move into the appropriate directory as shown below:

<pre>
python3 -m venv venv

# windows
venv\Scripts\activate.bat
# other 
source venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt
</pre>
A test should be carried out to ensure the setup has worked:
<pre>
pytest -v
</pre>


## Configuration

### *conf/config_meta.ini*


## Konfiguration
### *conf/config_meta.ini*

In the _config_meta.ini_ file, the metadata available from the OJS/OMP systems which ought to be exported in the corresponding XML files are marked. The schema can be expanded as required as long as values are used which are valid for the API request. 

Static values need to be marked in quotation marks and these are then not read. The examples used in this project for the OJS and OMP installations are available in folder ./_conf_.

### *conf/config.ini*
Please create this file from the *conf/config.ini.example* by renaming it.
All values are commented in the file.

## Start Export(SAF) / Import(DOI)
The script is ideally called by a cronjob.

<pre>
python journal2saf.py -c ./conf/config.ini -m ./conf/config_meta_ojs.ini
</pre>
 


## 


## License

see the LICENSE file
