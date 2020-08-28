import pytest
from jawiki import skkdict

d = skkdict.parse_skkdict('SKK-JISYO.jawiki', encoding='utf-8')

@pytest.mark.parametrize("yomi", [
    ('きんぐぬー'),
    ('れいわ'),
    ('うちだかおる'),
    ('さかもとふじえ'),
    ('あかとりい'),
    ('いせきしこく'),
    ('きうちきょう'),
    ('おおとにー'),
    ('いんだらじゃえいげんまりゅう'),
    ('こちらかつしかくかめありこうえんまえはしゅつじょ'),
])
def test_yomo(yomi):
    assert yomi in d

@pytest.mark.parametrize("kanji,yomi", [
    ('安蘇山', 'あそさん'),
    ('あに。' ,'あにまる'),
    ('南夕子' ,'みなみゆうこ'),
    ('青井惟董' ,'あおいこれただ'),
    ('赤プル' ,'あかぷる'),
    ('安藤孝子' ,'あんどうたかこ'),
    ('EX大衆' ,'いーえっくすたいしゅう'),
    ('古崤関' ,'ここうかん'),
    ('鬼滅の刃', 'きめつのやいば'),
    ('鬱多羅僧', 'うったらそう'),
    ('三衣一鉢', 'さんねいっぱつ'),
    ('中川幸永', 'なかがわゆきえ'),
    ('姶良サティ', 'あいらさてぃ'),
    ('青木十良', 'あおきじゅうろう'),
    ('穴門みかん', 'あなとみかん'),
])
def test_pair(kanji, yomi):
    print([kanji, yomi, d.get(yomi)])
    assert kanji in d.get(yomi)

@pytest.mark.parametrize("kanji,yomi", [
    # '''（初代）京山 華千代'''（きょうやま はなちよ、[[1904年]]（[[明治]]37年）[[8月11日]] - [[1983年]]（[[昭和]]58年）[[1月7日]]）
    # ('京山華千代' ,'きょうやまはなちよ'),
    ('お姉さま', 'ぼく'),
    ('109万本', 'いる'),
    ('擬餌状体', 'えすか'),
    ('銀河刑務所の囚人を全員脱獄させる。', 'えすか'),
    ('監督', 'あばんたいとる'),
    ('10代式守与太夫', 'しきもりよだゆう'),
])
def test_no_pair(kanji, yomi):
    assert yomi not in d or kanji not in d.get(yomi)

# はいっていてはいけないもの
@pytest.mark.parametrize("yomi", [
    ('いずれもろっくふぃるだむ'),
    ('のちの'),
    ('あーけーどすてぃっく'),
    ('ぐらびああいどる'),
    ('いわゆる'),
])
def test_not_in(yomi):
    assert yomi not in d

