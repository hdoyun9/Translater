import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from core import normalize
from terms import translate_terms,clean_glossary


class TermTests(unittest.TestCase):
    def test_half_width_and_combining_kana_share_glossary_key(self):
        self.assertEqual(normalize('ｶﾞﾀｶﾅ'),'ガタカナ')
        self.assertEqual(normalize('ｶﾀﾘﾅ'),'カタリナ')
        self.assertEqual(normalize('カ\u3099'),'ガ')

    def test_ocr_long_vowel_repairs_leave_numbers_and_english_intact(self):
        self.assertEqual(normalize('カタリナはコ - ヒ - を飲みます。'),'カタリナはコーヒーを飲みます。')
        self.assertEqual(normalize('コ一ヒ一'),'コーヒー')
        self.assertEqual(normalize('10 - 5 state-of-the-art パート一人'),'10 - 5 state-of-the-art パート一人')

    def test_dictionary_wins_over_automatic_name_and_corrects_particle(self):
        calls=[]
        def model(text,source):
            calls.append(text)
            return 'ZXQ100QXZ은 ZXQ101QXZ를 찾고 있습니다.'
        result=translate_terms('カタリナはオルステッドを探しています。','ja',model,
                               {'カタリナ':'카타리나','オルステッド':'오르스테드'})
        self.assertEqual(result,'카타리나는 오르스테드를 찾고 있습니다.')
        self.assertEqual(len(calls),1)

    def test_automatic_katakana_uses_consistent_standalone_translation(self):
        def model(text,source):
            return {'カタリナ':'카타리나','コーヒー':'커피',
                    'ZXQ100QXZはZXQ101QXZを飲みます。':'ZXQ100QXZ는 ZXQ101QXZ를 마십니다.'}[text]
        self.assertEqual(translate_terms('カタリナはコーヒーを飲みます。','ja',model,{}),
                         '카타리나는 커피를 마십니다.')

    def test_missing_markers_fall_back_without_dropping_terms_or_source_spans(self):
        calls=[]
        def model(text,source):
            calls.append(text)
            return 'broken' if 'ZXQ' in text else '<'+text+'>'
        result=translate_terms('前カタリナ中カタリナ後','ja',model,{'カタリナ':'카타리나'},False)
        self.assertEqual(result.count('카타리나'),2)
        for segment in ('前','中','後'): self.assertIn('<'+segment+'>',result)
        self.assertNotIn('ZXQ',result)

    def test_longest_matching_name_and_repeated_occurrences_survive(self):
        def model(text,source): return 'ZXQ100QXZ와 ZXQ101QXZ'
        result=translate_terms('ジョン・スミスとジョン','ja',model,
                              {'ジョン':'존','ジョン・スミス':'존 스미스'},False)
        self.assertEqual(result,'존 스미스와 존')

    def test_dictionary_remains_active_when_automatic_katakana_is_disabled(self):
        result=translate_terms('東京','ja',lambda text,source:'wrong',{'東京':'도쿄'},False)
        self.assertEqual(result,'도쿄')
        self.assertEqual(clean_glossary({'ｶﾀﾘﾅ':'카타리나','':'empty','bad':0}),{'カタリナ':'카타리나'})


if __name__=='__main__': unittest.main()
