import re
import jaconv
import html

from statistics import mean 

import Levenshtein

from jawiki.jachars import HIRAGANA_BLOCK, KANJI_BLOCK, KATAKANA_BLOCK, is_katakana_or_hiragana_or_nakaguro_or_space, is_katakana, is_kanji, is_hiragana, kanji_normalize
from jawiki.hojin import hojin_filter

NAMEISH_PATTERN = re.compile(r'([' + HIRAGANA_BLOCK + KANJI_BLOCK + KATAKANA_BLOCK + ']+)[\u0020\u3000]+([' + HIRAGANA_BLOCK + KANJI_BLOCK + KATAKANA_BLOCK + ']+)')

# きうちきょう /木内キヤウ/
HIRAGANA_NORMALIZER = str.maketrans('ゐゑをっあいうえおふぁぃぅぇぉゃゅょやゆよ', 'ーーーつーーーーーうあいうえおよよよよよよ')

INVALID_KANJI_PATTERNS = [
    re.compile(r'^\d+(月|世紀|年代)'),
    # 9代式守伊之助
    re.compile(r'^\d+代'),
    # TITLE<<Intel 4004>> KANJI<<4004>> YOMI<<よんまるまるよん>> 8
    re.compile(r'^[0-9]+$'),
    # '''10.『七変化狸御殿』'''（しちへんげ たぬきごてん）
    re.compile(r'^[0-9]+\.『'),
    # TITLE<<四川省>> KANJI<<{{仮リンク|巴蜀(歴史)|zh|巴蜀|label=巴蜀}}>> YOMI<<はしょく>> 4
    re.compile(r'\{\{仮リンク'),
    # r/^日本の企業一覧/, # TITLE<<日本の企業一覧 (その他製品)>> KANJI<<日本の企業一覧(その他製造)>> YOMI<<にほんのきぎょういちらんそのたせいぞう>> 19
    re.compile(r'^日本の企業一覧'),
    #   qr/の登場人物$/, # TITLE<<ときめきメモリアル2の登場人物>> KANJI<<ときめきメモリアル2の登場人物>> YOMI<<ときめきめもりあるつーのとうじょうじんぶつ>> 21
    re.compile(r'.*の登場(?:人物|キャラクター|仮面ライダー|怪獣|メカ|兵器|組織|馬|人物一覧|レスラー|人物の索引)$'),
    # '第43話 - 第45話', 'ものくろ'
    re.compile(r'第\d+話'),
]

def default_skip_logger(reason, line):
    print("<<<%s>>> %s" % (reason, line))

class WikipediaFilter:

    def __init__(self, skip_logger = default_skip_logger):
        self.skip_logger = skip_logger

    def log_skip(self, reason, line):
        self.skip_logger(reason, line)
        # print("<<<%s>>> %s" % (reason, line))

    def filter_entry(self, title, kanji, yomi):
        if kanji.startswith('[['):
            self.log_skip('kanji is page link', [kanji, yomi])
            return

        if not self.validate_phase1(title, kanji, yomi):
            return

        kanji = self.basic_filter(kanji)
        kanji = self.kanji_filter(kanji)
        yomi = self.basic_filter(yomi)
        yomi = self.yomi_filter(yomi, kanji)
        kanji, yomi = hojin_filter(kanji, yomi)

        # 全角スペースを半角に
        kanji = re.sub(r'\s', r' ', kanji)

        if not self.validate_phase2(kanji, yomi):
            return

        return (kanji, yomi)

    def validate_phase1(self, title, kanji, yomi):
        for yomi_prefix in ['[[', 'いま、', 'あるいは', 'もしくは', '▢']:
            if yomi.startswith(yomi_prefix):
                self.log_skip('ignorable yomi prefix: %s' % (yomi_prefix), [kanji, yomi])
                return False

        for kanji_prefix in ['』']:
            if kanji.startswith(kanji_prefix):
                self.log_skip('ignorable kanji prefix: %s' % (kanji_prefix), [kanji, yomi])
                return False

        # 「または」で始まるものは基本的に除外したほうがいいが、いくつかだけキャッチアップしよう。
        if yomi.startswith('または'):
            if len([1 for n in ['またはちろう', 'またはりひゃっかてん', 'またはり'] if yomi.startswith(n)])==0:
                self.log_skip('ignorable yomi prefix: %s' % (yomi_prefix), [kanji, yomi])
                return False

        if title in [
            # カッコ内に元になったマイクロンが入っているので無視。
            'トランスフォーマー ギャラクシーフォース',
            # 読み仮名が中途半端に入っている。古いアプリの情報なので一次情報をたどるのが難しくwikipedia川を修正するのが困難なので無視。
            'アイドル・ジェネレーション 第2次・萌えっ子大戦争!!',
            # ライトノベル独自用語
            'Dクラッカーズ',
        ]:
            self.log_skip('Title is in the blacklist', [title, kanji, yomi])
            return False

        return True

    def validate_phase2(self, kanji, yomi):
        if len(kanji) == 0:
            self.log_skip('kanji is empty', [kanji, yomi])
            return False

        if len(kanji) == 1:
            self.log_skip('kanji is single character', [kanji, yomi])
            return False

        if len(yomi) == 0:
            self.log_skip('yomi is empty', [kanji, yomi])
            return False

        if len(yomi) < 2:
            self.log_skip('yomi is too short', [kanji, yomi])
            return False

        if not is_hiragana(yomi):
            self.log_skip('yomi contains non-hiragana char', [kanji, yomi])
            return False

        if is_hiragana(kanji):
            self.log_skip('kanji is hiragana', [kanji, yomi])
            return False

        for kanji_prefix in ['〜', '『', '「', '＜', '〈','《', '／', '日本の']:
            if kanji.startswith(kanji_prefix):
                self.log_skip('kanji starts with %s' % kanji_prefix, [kanji, yomi])
                return False

        for kanji_postfix in ['・']:
            if kanji.endswith(kanji_postfix):
                self.log_skip('kanji ends with %s' % kanji_postfix, [kanji, yomi])
                return False

        for yomi_prefix in [
            # '''[[マイクロソフト]]'''（ただし、[[Xbox 360]]はどちらの規格にも対応せず、[[Microsoft Windows Vista]]は両規格に対応していた）
            'ただし、',
            # この音は'''ハーフ・ストップ'''（あるいはエコー、ハーフ・ミュート）と呼ばれる。
            'あるいは',
            'おりんぴっくの',]:
            if yomi.startswith(yomi_prefix):
                self.log_skip('yomi starts with %s' % yomi_prefix, [kanji, yomi])
                return False

        # yomi infx
        for infix in [
                # ''w3m'''（ダブリューサンエム または ダブリュースリーエム）
                ' または ',
                'における',
                "'''",
                '[',
            ]:
            if infix in yomi:
                self.log_skip('yomi contains %s' % infix, [kanji, yomi])
                return False

        # kanji infx
        for infix in [
                # '''Keyboard / kAoru ikArAshi / 五十嵐 馨'''（いからし かおる）
                '/',
                "''",
                '{{',
                '[[',
                '(',
                '（',
            ]:
            if infix in kanji:
                self.log_skip('kanji contains %s' % infix, [kanji, yomi])
                return False

        for pattern in INVALID_KANJI_PATTERNS:
            if pattern.match(kanji):
                self.log_skip('Invalid kanji pattern', [kanji, yomi])
                return False

        # katakana prefix
        m = re.match(r'^([' + KATAKANA_BLOCK + ']+)', kanji)
        if m:
            prefix = m[1]
            prefix_hira = jaconv.kata2hira(prefix).translate(HIRAGANA_NORMALIZER)
            normalized_yomi = yomi.translate(HIRAGANA_NORMALIZER)
            if not normalized_yomi.startswith(prefix_hira):
                self.log_skip("Kanji prefix and yomi prefix aren't same: normalized_yomi=%s prefix_hira=%s" % (normalized_yomi, prefix_hira), [kanji, yomi])
                return False

        # katakana postfix
        m = re.match(r'.*?([' + KATAKANA_BLOCK + ']+)$', kanji)
        if m:
            postfix = m[1]
            postfix_hira = jaconv.kata2hira(postfix).translate(HIRAGANA_NORMALIZER)
            normalized_yomi = yomi.translate(HIRAGANA_NORMALIZER)
            if not normalized_yomi.endswith(postfix_hira):
                self.log_skip("Kanji postfix and yomi postfix aren't same: normalized_yomi=%s postfix_hira=%s" % (normalized_yomi, postfix_hira), [kanji, yomi])
                return False

        return True

    def basic_filter(self, token):
        # &lt;ref&gt;1883(明治)年宣下、明治天皇&lt;/ref&gt;
        token = re.sub(r'&lt;ref.*', '', token)

        # token = re.sub(r'\{\{[Ll]ang-[a-z]+(?:-short)?\|.+?\}\}', '', token)

        # <!-- foobar -->
        token = re.sub(r'&lt;!--.*--&gt;', '', token)

        # '''[[葉状体]]'''（ようじょうたい）
        # '''[[瘀血]]証'''（おけつしょう）
        # token = re.sub(r'\[\[(.*)\]\]', r'\1', token)

        # '''池の平スノーパーク（旧白樺リゾートスキー場）'''（いけのたいらすのーぱーく）
        # '''砂川奈美(旧姓:伊藤)'''（いさがわなみ、[[1991年]][[1月23日]] - ）
        token = re.sub(r'（旧.*?）', r'', token)
        token = re.sub(r'[（\(](旧姓|本名)[:：].*?[）\)]', r'', token)
        token = re.sub(r'（(\d+|[一-九])代目?）', r'', token)
        token = re.sub(r'（初代）', r'', token)

        # token = re.sub(r'、.*', r'', token)

        # 先頭/末尾の中黒はマークアップ失敗なので、カバーしてあげる
        token = re.sub(r'^・', r'', token)
        token = re.sub(r'・$', r'', token)

        token = re.sub(r'&amp;', r'&', token)
        token = re.sub(r'(&(?:[a-z_-]+|#[0-9]+|#x[0-9A-Fa-f]+);)', lambda x: html.unescape(x[1]), token)

        return token.strip()

    def kanji_filter(self, kanji):
        # {{lang|en|AMBAC}}
        kanji = re.sub(r'\{\{lang\|[a-zA-Z_-]+\|(.+?)\}\}', r'\1', kanji)

        # {{CP932フォント|髙}}千代酒造
        # '''司馬 {{JIS2004フォント|遼󠄁}}太郎'''
        # つじかおり /{{JIS90フォント|辻}}香緒里/
        # {{Anchor|穴子包丁}}
        # うじょう /{{Vanchor|羽状}}/
        # まっちでーじぇいりーぐ /マッチデー{{unicode|♥}}Jリーグ/
        # '''{{linktext|六根}}'''（ろっこん）
        kanji = re.sub(r'\{\{(?:En|IPA-en|要出典範囲|linktext|unicode|Anchor|Vanchor|[A-Z0-9]+フォント)\|(.+)\}\}', r'\1', kanji)

        # [[ページ名|リンクラベル]] 
        kanji = re.sub(r'\[\[(?:.*)\|(.*)\]\]', r'\1', kanji)
        kanji = re.sub(r'\[\[(.*)\]\]', r'\1', kanji)

        kanji = re.sub(r'\s+', r' ', kanji)

        # '山田 太朗' → 山田太朗
        while True:
            kanji, number_of_subs_made = re.subn(NAMEISH_PATTERN, r'\1\2', kanji)
            if number_of_subs_made==0:
                break

        return kanji

    def yomi_filter(self, yomi, kanji=''):
        # [[慶應]]3年
        # yomi = re.sub(r"\[\[[" + KANJI_BLOCK + "]+\]\]\d+年.*", '', yomi)
        pyomi = yomi
        while True:
            yomi = re.sub(r"^のちの('''|\[\[).*", '', yomi)
            yomi = re.sub(r'、声 - .*', '', yomi)
            yomi = re.sub(r'\[\[\d+年\]\].*', '', yomi)
            yomi = re.sub(r'\[\[\d+月\d+日\]\].*', '', yomi)
            yomi = re.sub(r"''.*", '', yomi)
            yomi = re.sub(r"\{\{.*", '', yomi)
            yomi = re.sub(r'\d+月\d+日.*', '', yomi)
            yomi = re.sub(r'\?\s*-\s*$', '', yomi)
            yomi = re.sub(r'[、][a-zA-Z]+[' + KANJI_BLOCK + ']+$', '', yomi)
            yomi = re.sub(r'[、][' + KANJI_BLOCK + ']+$', '', yomi)
            yomi = re.sub(r'[、][「].*', '', yomi)
            yomi = re.sub(r'(?:[' + KANJI_BLOCK + ']+)?([0-9?]+|元)年.*', '', yomi)
            yomi = re.sub(r'(生年不詳|生年月日非公表|生没年不詳).*', '', yomi)
            yomi = re.sub(r'現在の芸名.*', '', yomi)
            yomi = re.sub(r'\[\[[' + KANJI_BLOCK + ']+]].*', '', yomi)
            yomi = re.sub(r'(?:英文(名称|表記)|旧名|現姓|旧姓|通称|英文名|原題|ドイツ語|英語|英語表記|英語名称|英文社名|オランダ語|満州語|旧|旧芸名|中国語簡体字|漢語名字|略称|本名|英称|英)[:：；;は・].*', '', yomi)
            yomi = re.sub(r'[（:：,]\s*$', '', yomi)
            yomi = re.sub(r'[,、][（:：,]\s*$', '', yomi)
            yomi = re.sub(r'[,、]\[\[.*$', '', yomi)
            yomi = re.sub(r'''[、,][ A-Za-z.'&]+$''', '', yomi)
            yomi = re.sub(r'''[、,][ A-Za-z.'-''' + KANJI_BLOCK + ''']+$''', '', yomi)
            yomi = re.sub(r'、[（:：\-]*[ A-Za-z]+$', '', yomi)
            yomi = re.sub(r'、(略称|詳しくは|本名\s*同じ|単に).*$', '', yomi)
            yomi = re.sub(r'[？?、－]+\s*$', '', yomi)
            yomi = re.sub(r'\s*$', '', yomi)
            yomi = re.sub(r'\[\[$', '', yomi)

            if pyomi == yomi:
                break
            else:
                pyomi = yomi

        # remove spaces in yomi
        yomi = re.sub(r'\s+', r'', yomi)

        yomi = jaconv.kata2hira(yomi)

        yomi = self.filter_yomi_entities(kanji, yomi)

        # アイエスオー、イソ、アイソ to アイエスオー
        if all([is_katakana_or_hiragana_or_nakaguro_or_space(s) for s in yomi.split('、')]):
            yomi = yomi.split('、')[0]

        if '、' in yomi:
            yomi = "、".join([s for s in yomi.split('、') if kanji != kanji_normalize(s)])

        return yomi

    def filter_yomi_entities(self, kanji, yomi):
        entities = yomi.split('、')

        results = []
        for s in entities:
            # `今鷹 真（今鷹 眞、いまたか まこと 1934年2月28日- ）` のように、旧字体の場合は無視する。
            if kanji_normalize(s) == kanji:
                continue
            if not is_katakana_or_hiragana_or_nakaguro_or_space(s):
                break
            results.append(s)

        # 森ガールの集い（かまいたち、オレンジサンセット、ヒカリゴケ、しゃもじ） みたいなやつはまとめて消す
        # ただし、「しなぬのくにのみやつこ /科野国造/」のような、日本古来の固有名詞に関しては、読み方の揺れが大きいので除外する。
        # '''袁 牧之'''（えん ぼくし、ユエン・ムーチー、ユアン・ムーチー、イエン・ムーツー） みたいなケースも救う
        if len(results) > 3:
            base = results[0]
            if not base.endswith('みやつこ') and not base.startswith('えん'):
                score = mean([Levenshtein.distance(results[0], r) for r in results[1:]])
                if score > 5:
                    print("TOOMUCHRESULTS:: " + str(results) + ' ' + str(score))
                    return ''

        return '、'.join(results)

