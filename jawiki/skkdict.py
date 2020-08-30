import re


def parse_skkdict(path, encoding='euc-jp'):
    result = {}

    with open(path, 'r', encoding=encoding) as fp:
        for line in fp:
            if line.startswith(';;'):
                continue

            m = line.strip().split(' ', 1)
            yomi, kanjis = m
            kanjis = kanjis.lstrip('/').rstrip('/').split('/')
            kanjis = [re.sub(';.*', '', k) for k in kanjis]

            result[yomi] = set(kanjis)

    return result


def merge_skkdict(dicts):
    result = {}

    for dic in dicts:
        for k, v in dic.items():
            if k not in result:
                result[k] = []
            result[k].extend(v)

    return result


def write_skkdict(outfname, dictionary):
    with open(outfname, 'w', encoding='utf-8') as ofh:
        for yomi in sorted(dictionary.keys()):

            kanjis = dictionary[yomi]
            if len(kanjis) != 0:
                ofh.write("%s /%s/\n" % (yomi, '/'.join(kanjis)))
#            if len(kanjis) > 20:
#                logging.info("This entry contains too many kanjis: %s -> %s" % (yomi, kanjis))
