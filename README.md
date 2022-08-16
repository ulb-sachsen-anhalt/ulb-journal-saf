# Harvesting of datasets from the ULB Sachsen-Anhalt's OJS/OMP installations to a DSpace based Repository


## General Goals 

Automatic publication of contents of OJS and OMP resources (journals, series, monographs) in a DSpace 6.3 repository.
DOI registration of exported contents via the DSpace repository.
Return and store the DOI metadata information into the OJS and OMP systems.



## 1. Metadata retrieval in OJS/OMP

In this first step the python script _journal2saf.py_ is used to get all relevant metadata for the resource in a given [OMP](https://pkp.sfu.ca/omp) or [OJS](https://pkp.sfu.ca/ojs/) server which are marked already as **published** and that are to be sent to DSpace. This is done via the [REST-API](https://docs.pkp.sfu.ca/dev/api/ojs/3.3). It will only export resources that have not been exported with it yet.
 
## 2. Creation of SAF-Data Packages for the import and copying to DSpace

The script then converts the extracted data from OJS/OMP into the [SAF Archive](https://wiki.lyrasis.org/display/DSDOC5x/Importing+and+Exporting+Items+via+Simple+Archive+Format) format which is used by DSpace installations to import data into a standard DSpace collection. These data are saved in a previously defined export folder. 

Once in this folder, the newly created SAF-Archive files are then copied/exported to the target DSpace installation using _scp_ into a previously defined folder. 


## 3. Import and DOI creation on DSpace
On the DSpace server, a bash script is then used to automatically import SAF files and also to export a list of all newly created [DOIs](https://www.doi.org/) by the DSpace installation which processes the new data files.

<pre>
 ./dspace/bin/journals_import.sh
</pre>
You may need to change the script to work with your local DSpace instance.

The following directory structure needs to exist on the DSpace server:
<pre>
~/&lt;exchange_folder>/source
~/&lt;exchange_folder>/doi
~/&lt;exchange_folder>/map
</pre>

## 4. DOI Information checks in DSpace and storage in the metadaten schema of OJS/OMP
Everytime _journal2saf.py_ is executed, the script checks if DOIs from SAF files which have been already exported to DSpace are available on the DSpace server. If it finds new DOIs, they get copied onto the OJS/OMP server.

&#9755; For each resource ((a _galley_ or _publicationFormat_) in OJS/OMP terminology) in a journal an external URL can be stored in the field ([urlRemote](https://docs.pkp.sfu.ca/dev/api/ojs/3.1#tag/Submissions/paths/~1submissions~1{submissionId}/get))


If the _conf/config.ini_ setting "update_remote" is true, the script _journal2saf.py_ ensures that the newly available DOIs are stored in OJS/OMP as the *urlRemote* attribute for each publication. For this to work properly, the OJS/OMP Plugin [SetRemoteUrlPlugin](https://github.com/ulb-sachsen-anhalt/setRemoteUrlPlugin) must be previously installed.


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

### Mandatory

#### *conf/config.ini*
You need to create this file from the *conf/config.ini.example* by renaming it.
All values are commented in the file. Values that need to be changed are marked with &lt;>

#### *conf/config_meta.ini*

In the _config_meta.ini_ file, the metadata available from the OJS/OMP system which should be exported in the corresponding XML files are marked. The schema can be expanded as required as long as values which are valid for the API request are used.

Static values need to be marked in quotation marks and these are then not read. The examples used in this project for the OJS and OMP installations are available in folder ./_conf_.

### Optional

#### *Filtering of Metadata*

In some cases, given metadata needs some filtering before being added to DSpace. For more information on how to filter metadata before exporting, see the file *./lib/filters.py*.

## Start Export(SAF) / Import(DOI)
The script is ideally called by a cronjob.

<pre>
python journal2saf.py -c ./conf/config.ini -m ./conf/config_meta_ojs.ini
</pre>
 


## 


## License

see the LICENSE file
