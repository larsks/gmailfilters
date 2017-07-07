import logging

LOG = logging.getLogger(__name__)

def chunker(items, chunksize):
    '''Splits a list into lists of chunksize items.'''

    for i in range(0, len(items), chunksize):
        yield items[i:i+chunksize]
