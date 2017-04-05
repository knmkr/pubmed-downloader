# pmdl: PubMed Downloader

Download full text pdf and supplemental materials for each PubMed IDs.

## Install

```
$ pip install -r requirements.txt
```

## How to use

```
$ pmdl --pubmed-ids <pubmed id> <pubmed id> <pubmed id> ...
```

Eg.

```
$ pmdl --pubmed-ids 26752266
```

**Supported sources**

- `Nat Genet` (eg, PMID: `26752266`, PMID: `25774636` (non-open access))
- `PLoS Genet/One` (eg, PMID: `17447842`)
- `OXFORD JOURNALS` (eg, PMID: `23612905`)
- `PMC` (eg, PMID: `21572416`)

**License**

- MIT
