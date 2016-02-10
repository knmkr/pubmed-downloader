#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
import time
import argparse

from pmdl import *
from errors import *
from utils import *


def main():
    parser = argparse.ArgumentParser(description='Download full text pdf and supplemental materials for each PubMed IDs.')
    parser.add_argument('--pubmed-ids',      nargs='+', required=True, help='PubMed IDs')
    parser.add_argument('--dst-dir',         default='.',              help='Destination directory')
    parser.add_argument('--with-pmc',        action='store_true',      help='Allow downloading from PMC. Default: False')
    parser.add_argument('-w', '--overwrite', action='store_true',      help='Allow overwriting if downloaded files already exist. Default: False')
    args = parser.parse_args()

    downloaders = [
        (r'.*dx.doi.org/[\d\.]+/ng[\d\.]+', nat_genet_downloader),  # Nat Genet
        (r'.*plos.org.*', plos_downloader),                         # PLoS Genet, PLoS One
        (r'.*oxfordjournals.org.*', oxford_journals_downloader),    # Hum Mol Genet
    ]

    if args.with_pmc:
        downloaders += [('.*www.ncbi.nlm.nih.gov/pmc.*', pmc_downloader)]

    for pubmed_id in args.pubmed_ids:
        print '[INFO] Pubmed ID:', pubmed_id

        try:
            # Get publisher information
            publisher_links = get_publisher_links(pubmed_id)

            # Select downloader by publisher information
            downloader = None
            for link in publisher_links:
                for pattern, _downloader in downloaders:
                    if re.match(pattern, link):
                        publisher_link, downloader = link, _downloader
                        break

            if not downloader:
                raise PubmedPdfDownloaderError('Not supported publisher')

            # Download full text and supplemental materials
            downloader(pubmed_id, publisher_link, args)

        except PubmedPdfDownloaderError as e:
            print '[ERROR] PMID', pubmed_id, e
            time.sleep(5)
        except (requests.exceptions.MissingSchema,
                requests.exceptions.ConnectionError,
                requests.exceptions.ReadTimeout) as e:
            print '[ERROR] PMID', pubmed_id, 'URL maybe broken, or network error', e


if __name__ == '__main__':
    main()
