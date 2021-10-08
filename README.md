# How to Run

## Running on ADA

```bash
$ sinteractive
$ module load python/3.8.3
```

## Create a Virtual Environment

```bash
$ python3 -m venv ire_phase_1
$ source <path_to_ire_phase_1>/bin/activate
```

## Install Dependencies

```bash
$ pip3 install -r requirements.txt
```

## Index Creation

```bash
$ bash index.sh <path_to_wiki_dump> <path_to_inverted_index> stats.txt
```

## Search

```bash
$ bash search.sh <path_to_inverted_index> <query_file>
```

# Code Structure

## Indexer.py

This is the main indexing file. It parses the documents using the SAX parser and send each document for processing.
After processing the postings list of each document are merged until a certain threshold and then written as the stage 1
index. Similarly, the titles are also written into a separate file for displaying in the search. After creation of the
stage 1 index, we merge these files and create smaller files to increase read speed while searching and this is done by
merging the overlapping tokens in the stage 1 index to finally write the stage 2 index. Additional files such as stats
file, file containing first words in index2 for binary search and the page count are also written at the end.

The index is split up into 4 components:

- index2_*.txt files which contain the postings list for each token
- title_*.txt files which contain document titles
- page_count.txt which contains total number of documents in the dump
- first_words.txt which contain the first token present in each index file

## Processing.py

This file is responsible for the pre-processing i.e., lower case, tokenization, stop word removal, stemming, and
cleaning of the title, and text content of the documents and created the posting list of the tokens present in the
document. It also identifies the various sections of the text such as references, links, categories, infobox and body
using python regex and assigns appropriate tags to each token depending upon where that token is found in the document
along with the frequency of each token in a particular document.

## Stopwords.py

This file contains all the stopwords which are removed in the pre-processing step

## Search.py

This file is responsible for handling the queries for search. It tokenizes the queries, finds the necessary files for
index reading using binary search, reads the necessary index for finding the necessary postings list and document IDs,
calculates the score of each document for the given query using BM25 and then ranks them on the basis of the score
obtained. The top 10 Doc ID - Title pairs are shown to the user as the final result. 