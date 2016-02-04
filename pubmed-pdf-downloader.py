#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import re
import urlparse
import argparse

from lxml import html
import requests

from errors import *
from utils import *


# TODO: install and execute as pypi package. cf. local install of py-vcf-parser
def main():
    parser = argparse.ArgumentParser(description='Downlaod open access full text pdf and supplemental materials of each PubMed IDs.')
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
            print '[ERROR]', e


def nat_genet_downloader(pubmed_id, publisher_link, args):
    '''Download from Nat Genet

    E.g.
    - open access: 26752266
    - non-open access: 25774636
    '''

    print '[INFO] Try to download from Nat Genet'

    response = requests.get(publisher_link)

    if str(response.status_code) == '401':
        raise PubmedPdfDownloaderError('Failed. Maybe not open access article')
    elif str(response.status_code) != '200':
        raise PubmedPdfDownloaderError('Failed. Status code: {}'.format(response.status_code))

    url = response.url
    # pdf_url = os.path.join(os.path.dirname(os.path.dirname(url)), 'pdf', os.path.basename(url) + '.pdf')


def plos_downloader(pubmed_id, publisher_link, args):
    '''Download from PLoS Genet/One

    E.g.
    - open access PLoS Genet: 17447842 17658951
    - open access PLoS One: 17684544
    '''

    print '[INFO] Try to download from PLoS Genet/One'

    if 'journal.pgen' in publisher_link:
        base = '/plosgenetics'
    elif 'journal.pone' in publisher_link:
        base = '/plosone'
    else:
        raise PubmedPdfDownloaderError('Unexpected url for plos_downloader: ' + publisher_link)

    response = requests.get(publisher_link)

    if str(response.status_code).startswith('4'):
        raise PubmedPdfDownloaderError('Failed. Status code: {}'.format(response.status_code))

    # Get link to supplemental materials
    body = html.fromstring(response.content)
    supplemental_file_urls = [absolute_url(response, url, base=base) for url in body.xpath('//h2[text()="Supporting Information"]/following-sibling::*//a/@href') if not url.startswith('#')]

    print '[DEBUG] supplemental_file_urls', supplemental_file_urls

    # Download full text pdf
    pdf_urls = body.xpath('//a[text()="Download PDF"]/@href')

    if not pdf_urls:
        raise PubmedPdfDownloaderError('Full text pdf not found')

    pdf_url = absolute_url(response, pdf_urls[0])
    download_file(pdf_url, os.path.join(args.dst_dir, 'PMID{pmid}.pdf'.format(pmid=pubmed_id)), overwrite=args.overwrite)

    # Download supplemental materials
    if not supplemental_file_urls:
        print '[WARN] Supplemental materials not found'
        return

    for i, supplemental_file_url in enumerate(supplemental_file_urls):
        _, extention = os.path.splitext(supplemental_file_url)
        download_file(supplemental_file_url, os.path.join(args.dst_dir, 'PMID{pmid}_S{i}{extention}'.format(pmid=pubmed_id, i=i+1, extention=extention)), overwrite=args.overwrite)
    return


def oxford_journals_downloader(pubmed_id, publisher_link, args):
    '''Downlaod from OXFORD JOURNALS

    E.g.
    - open access: 23612905 25628336
    - non-open access: 25429064
    '''

    print '[INFO] Try to download from OXFORD JOURNALS'

    # FIXME *.oxfordjournals.org?
    url = 'http://hmg.oxfordjournals.org/cgi/pmidlookup?pmid={pmid}'.format(pmid=pubmed_id)
    response = requests.get(url)

    if str(response.status_code).startswith('4'):
        raise PubmedPdfDownloaderError('Failed. Status code:{}'.format(response.status_code))

    # Get link to supplemental materials
    body = html.fromstring(response.content)
    supplemental_relative_urls = body.xpath('//a[text()="Supplementary Data"]/@href')

    # Download full text pdf
    pdf_url = response.url.strip('/') + '.full.pdf'
    download_file(pdf_url, os.path.join(args.dst_dir, 'PMID{pmid}.pdf'.format(pmid=pubmed_id)), overwrite=args.overwrite)

    # Download supplemental materials
    if not supplemental_relative_urls:
        print '[WARN] Supplemental materials not found'
        return

    supplemental_url = absolute_url(response, supplemental_relative_urls[0])
    response = requests.get(supplemental_url)
    body = html.fromstring(response.content)
    supplemental_file_urls = [absolute_url(response, href) for href in body.xpath('//h2[text()="Supplementary Data"]/following-sibling::ul/li/a/@href')]

    if not supplemental_file_urls:
        raise PubmedPdfDownloaderError('Link to supplemental materials exists, but files not found')

    for i, supplemental_file_url in enumerate(supplemental_file_urls):
        _, extention = os.path.splitext(supplemental_file_url)
        download_file(supplemental_file_url, os.path.join(args.dst_dir, 'PMID{pmid}_S{i}{extention}'.format(pmid=pubmed_id, i=i+1, extention=extention)), overwrite=args.overwrite)

    return


def pmc_downloader(pubmed_id, publisher_link, args):
    '''Downlaod from PMC

    E.g.
    - 21572416 25187374
    '''

    print '[INFO] Try to download from PMC'

    pdf_url = 'http://www.ncbi.nlm.nih.gov/pmc/articles/pmid/{pmid}/pdf'.format(pmid=pubmed_id)
    download_file(pdf_url, os.path.join(args.dst_dir, 'PMID{pmid}.pdf'.format(pmid=pubmed_id)), overwrite=args.overwrite)

    url = 'http://www.ncbi.nlm.nih.gov/pmc/articles/pmid/{pmid}'.format(pmid=pubmed_id)
    response = requests.get(url)
    body = html.fromstring(response.content)
    # FIXME
    supplemental_file_urls = body.xpath('//h2[text()="Supplementary Material" or text()="SUPPLEMENTARY MATERIAL" or text()="Supplemental Data" or text()="SUPPLEMENTAL DATA"]/parent::node()/descendant::*/a/@href')

    # TBD: use PMC API? (http://europepmc.org/RestfulWebService#suppFiles)

    i = 1
    for url in supplemental_file_urls:
        url = absolute_url(response, url)

        try:
            _, extention = os.path.splitext(url)
            download_file(url, os.path.join(args.dst_dir, 'PMID{pmid}_S{i}{extention}'.format(pmid=pubmed_id, i=i, extention=extention)), overwrite=args.overwrite)
            i += 1
        except PubmedPdfDownloaderError as e:
            # External link to supplementary materials
            print '[INFO] External link found:', url
            response = requests.get(url)
            body = html.fromstring(response.content)
            ext_urls = [os.path.join(os.path.dirname(response.url), link) for link in body.xpath('//a/@href')]

            for ext_url in ext_urls:
                _, extention = os.path.splitext(ext_url)
                download_file(ext_url, os.path.join(args.dst_dir, 'PMID{pmid}_S{i}{extention}'.format(pmid=pubmed_id, i=i, extention=extention)), overwrite=args.overwrite)
                i += 1

    return


if __name__ == '__main__':
    main()
