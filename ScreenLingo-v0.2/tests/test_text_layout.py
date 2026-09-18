from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from core import normalize
from text_layout import make_line,assemble_blocks,sentence_units,tile_boxes
from translate_local import split_for_model


def line(text,x,y,vertical=False,source='ja'):
    return make_line([dict(text=c,box=[x+(0 if vertical else i*22),y+(i*22 if vertical else 0),20,20])
                     for i,c in enumerate(text)],source)


class LayoutTests(unittest.TestCase):
    def test_cjk_spaces_removed_but_english_spaces_preserved(self):
        self.assertEqual(normalize('こ の 扉 を 開 け て 、 鍵 を 探 し て 。'),'この扉を開けて、鍵を探して。')
        self.assertEqual(normalize('Open the door.'),'Open the door.')

    def test_vertical_columns_read_right_to_left(self):
        blocks=assemble_blocks([line('鍵を探して。',150,10,True),line('扉を開けて、',200,10,True)])
        self.assertEqual(len(blocks),1)
        self.assertEqual(blocks[0]['text'],'扉を開けて、鍵を探して。')
        self.assertEqual(blocks[0]['direction'],'vertical')

    def test_wrapped_lines_join_before_translation(self):
        a=dict(text='Open this door and',source='en',box=[10,10,240,20],direction='horizontal',em=20,source_boxes=[[10,10,240,20]])
        b=dict(text='look for the key.',source='en',box=[10,45,220,20],direction='horizontal',em=20,source_boxes=[[10,45,220,20]])
        self.assertEqual(assemble_blocks([b,a])[0]['text'],'Open this door and look for the key.')

    def test_separate_bubbles_are_not_joined(self):
        self.assertEqual(len(assemble_blocks([line('こんにちは。',20,10),line('さようなら。',350,180)])),2)

    def test_more_than_sixty_lines_survive(self):
        blocks=assemble_blocks([line('文です。',10,i*100) for i in range(75)])
        self.assertEqual(len(blocks),75)

    def test_ruby_is_attached_to_kanji_and_still_masked(self):
        body=line('扉を開ける',100,20,True)
        ruby=make_line([dict(text=c,box=[124,20+i*8,7,7]) for i,c in enumerate('とびら')],'ja')
        blocks=assemble_blocks([ruby,body])
        self.assertEqual(len(blocks),1)
        self.assertEqual(blocks[0]['text'],'扉を開ける')
        self.assertEqual(blocks[0]['readings'],['とびら'])
        self.assertEqual(len(blocks[0]['source_boxes']),8)

    def test_sentence_splitting_keeps_last_character(self):
        self.assertEqual(sentence_units('こんにちは。次です！終わり'),['こんにちは。','次です！','終わり'])
        self.assertEqual(sentence_units('Open the door. Find the key.'),['Open the door.','Find the key.'])

    def test_model_chunks_preserve_long_input(self):
        class Tokenizer:
            def encode(self,text,out_type): return list(text)
        text='a'*500+'、'+'b'*900+'終'
        chunks=split_for_model(text,Tokenizer(),64)
        self.assertEqual(''.join(chunks),text)
        self.assertTrue(all(len(c)<=64 for c in chunks))

    def test_tiles_cover_full_image_without_downsampling(self):
        boxes=tile_boxes(4000,2200,1800)
        self.assertEqual(max(b[2] for b in boxes),4000)
        self.assertEqual(max(b[3] for b in boxes),2200)
        for x in range(0,4000,25):
            for y in range(0,2200,25):
                self.assertTrue(any(a<=x<c and b<=y<d for a,b,c,d in boxes))


if __name__=='__main__': unittest.main()
