"""OCR reading order, paragraph assembly and lossless sentence splitting."""
import re
from statistics import median
from core import normalize, source_for, intersection_over_union


def union_box(boxes):
    left=min(b[0] for b in boxes); top=min(b[1] for b in boxes)
    return [left,top,max(b[0]+b[2] for b in boxes)-left,
            max(b[1]+b[3] for b in boxes)-top]


def reading_direction(words, requested='auto'):
    if requested in ('horizontal','vertical'):
        return requested
    if len(words)<2:
        return 'horizontal'
    centers=[(w['box'][0]+w['box'][2]/2,w['box'][1]+w['box'][3]/2) for w in words]
    dx=max(x for x,y in centers)-min(x for x,y in centers)
    dy=max(y for x,y in centers)-min(y for x,y in centers)
    return 'vertical' if dy>dx*1.8 else 'horizontal'


def make_line(words, source, requested='auto'):
    direction=reading_direction(words,requested if source in ('ja','zh') else 'horizontal')
    words=sorted(words,key=lambda w:w['box'][1] if direction=='vertical' else w['box'][0])
    text=normalize(' '.join(w['text'] for w in words))
    dimensions=[min(w['box'][2:]) for w in words if len(w['text'])<=2 and min(w['box'][2:])>3]
    em=median(dimensions) if dimensions else median(w['box'][3] for w in words)
    return dict(text=text,source=source,box=union_box([w['box'] for w in words]),
                direction=direction,em=max(em,4),source_boxes=[w['box'] for w in words],words=words)


def dedupe_lines(lines):
    # Prefer a full tile's text to a clipped repeat at an overlap boundary.
    result=[]
    japanese_context=any(len(re.findall(r'[\u3040-\u30ff]',l['text']))>=2 for l in lines if l['source']=='ja')
    def rank(line):
        text=line['text']
        kana=len(re.findall(r'[\u3040-\u30ff]',text)); han=len(re.findall(r'[\u3400-\u9fff]',text))
        latin=len(re.findall(r'[A-Za-z]',text))
        if line['source']=='ja' and kana>=2: score=4
        elif han and line['source']=='ja' and japanese_context: score=3.5
        elif han and line['source']=='zh': score=3
        elif han: score=2.5
        elif latin and line['source']=='en': score=2
        else: score=1
        return score,len(text)
    for line in sorted(lines,key=rank,reverse=True):
        duplicate=False
        for existing in result:
            a,b=line['box'],existing['box']
            overlap=intersection_over_union(a,b)
            if overlap>.55 or (overlap>.25 and
                normalize(line['text']) in normalize(existing['text'])):
                duplicate=True; break
        if not duplicate:
            result.append(line)
    return result


def _adjacent(a,b):
    if a['source']!=b['source'] or a['direction']!=b['direction']:
        return False
    if max(a['em'],b['em'])/min(a['em'],b['em'])>1.65:
        return False
    x,y,w,h=a['box']; X,Y,W,H=b['box']
    em=max(a['em'],b['em'])
    if a['direction']=='vertical':
        gap=max(x,X)-min(x+w,X+W)
        overlap=max(0,min(y+h,Y+H)-max(y,Y))/max(1,min(h,H))
        return -.2*em<=gap<=1.65*em and overlap>.45
    gap=max(y,Y)-min(y+h,Y+H)
    overlap=max(0,min(x+w,X+W)-max(x,X))/max(1,min(w,W))
    return -.2*em<=gap<=1.5*em and (overlap>.35 or abs(x-X)<em)


def assemble_blocks(lines):
    lines=dedupe_lines(lines)
    # Small kana directly beside a kanji are its pronunciation (furigana),
    # not another sentence. Preserve their masks/reading without translating
    # the pronunciation as an unrelated word such as a sound effect.
    readings=set()
    for i,ruby in enumerate(lines):
        if ruby['source']!='ja' or not re.fullmatch(r'[\u3040-\u30ff]{2,14}',ruby['text']): continue
        rx,ry,rw,rh=ruby['box']
        matches=[]
        for j,body in enumerate(lines):
            if i==j or body['source']!='ja' or ruby['em']>body['em']*.6: continue
            if ruby['direction']!=body['direction']: continue
            for word in body.get('words',[]):
                if not re.search(r'[\u3400-\u9fff]',word['text']): continue
                x,y,w,h=word['box']
                if body['direction']=='vertical':
                    gap=rx-(x+w)
                    overlap=max(0,min(y+h,ry+rh)-max(y,ry))/max(1,min(h,rh))
                else:
                    gap=y-(ry+rh)
                    overlap=max(0,min(x+w,rx+rw)-max(x,rx))/max(1,min(w,rw))
                if -2<=gap<=body['em']*.8 and overlap>.7:
                    matches.append((gap,j))
        if matches:
            owner=lines[min(matches)[1]]
            owner['source_boxes']=owner['source_boxes']+ruby['source_boxes']
            owner.setdefault('readings',[]).append(ruby['text'])
            readings.add(i)
    lines=[line for i,line in enumerate(lines) if i not in readings]
    groups=[]
    pending=set(range(len(lines)))
    while pending:
        seed=min(pending); pending.remove(seed)
        group=[seed]; queue=[seed]
        while queue:
            current=queue.pop()
            neighbors=[i for i in sorted(pending) if _adjacent(lines[current],lines[i])]
            for i in neighbors:
                pending.remove(i); group.append(i); queue.append(i)
        groups.append([lines[i] for i in group])
    blocks=[]
    for group in groups:
        vertical=group[0]['direction']=='vertical'
        group.sort(key=lambda l:(-l['box'][0],l['box'][1]) if vertical else (l['box'][1],l['box'][0]))
        text=''
        for line in group:
            part=line['text']
            if text.endswith('-') and group[0]['source']=='en' and part[:1].islower():
                text=text[:-1]+part
            else:
                text=normalize(text+' '+part)
        source=source_for(text,group[0]['source'])
        if source is None and re.search(r'[\uac00-\ud7a3]',text):
            source='keep'
        elif source is None:
            source='unreadable' if re.search(r'[?\ufffd\u2047]',text) else 'keep'
        boxes=[box for line in group for box in line['source_boxes']]
        blocks.append(dict(text=text,source=source,box=union_box(boxes),
                           source_boxes=boxes,direction=group[0]['direction'],
                           readings=[r for line in group for r in line.get('readings',[])]))
    # Recognizers disagree on line breaks; remove their duplicate paragraphs too.
    return sorted(dedupe_lines(blocks),key=lambda b:(round(b['box'][1]/30),-b['box'][0] if b['direction']=='vertical' else b['box'][0]))


def sentence_units(text):
    """Keep every input character; split at real punctuation, never OCR lines."""
    return [unit.strip() for unit in re.findall(
        r'.+?(?:[。！？!?]+[」』\"\']*|\.[\"\']*(?=\s|$)|\n+|$)',text,re.S) if unit.strip()]


def tile_boxes(width,height,limit,overlap=100):
    def starts(size):
        values=[0]
        while values[-1]+limit<size:
            values.append(min(values[-1]+limit-overlap,size-limit))
        return values
    return [(x,y,min(width,x+limit),min(height,y+limit))
            for y in starts(height) for x in starts(width)]
