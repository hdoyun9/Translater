"""Exact user terminology and consistent katakana, without silent marker loss."""
import re
from core import normalize

KATAKANA = r'[ァ-ヺー]{2,}(?:・[ァ-ヺー]+)*'


def clean_glossary(value):
    if not isinstance(value,dict): return {}
    return {normalize(k):normalize(v) for k,v in value.items()
            if isinstance(k,str) and isinstance(v,str) and normalize(k) and normalize(v)}


def correct_particle(text,term):
    if not term or not ('가'<=term[-1]<='힣'): return text
    final=(ord(term[-1])-ord('가'))%28
    pairs={'은':('은','는'),'는':('은','는'),'이':('이','가'),'가':('이','가'),
           '을':('을','를'),'를':('을','를'),'과':('과','와'),'와':('과','와'),
           '으로':('으로','로'),'로':('으로','로')}
    match=re.match(r'(으로|은|는|이|가|을|를|과|와|로)(?=$|[\s,.!?。]|[도만의])',text)
    if match:
        particle=match[0]
        consonant=bool(final) and not (particle in ('으로','로') and final==8)
        return pairs[particle][0 if consonant else 1]+text[len(particle):]
    return text


def translate_terms(text,source,translate,glossary,katakana=True):
    """Translate whole sentences with stable term markers; verify every occurrence.

    Unknown katakana uses the local model's standalone reading, not a guessed
    official name. The user's glossary takes precedence, including kanji names.
    """
    keys=sorted(glossary,key=len,reverse=True)
    patterns=[re.escape(key) for key in keys]
    if source=='ja' and katakana: patterns.append(KATAKANA)
    if not patterns: return translate(text,source)
    spans=[]
    for match in re.finditer('|'.join(patterns),text):
        original=match[0]
        if original in glossary: target=glossary[original]
        else:
            # A name missing from the model stays legible as its original text.
            try: target=translate(original,source)
            except RuntimeError: target=original
        spans.append((match.start(),match.end(),target))
    if not spans: return translate(text,source)
    if len(spans)==1 and spans[0][:2]==(0,len(text)): return spans[0][2]
    counter=100
    marked=''; end=0; replacements=[]
    for start,stop,target in spans:
        marker=f'ZXQ{counter}QXZ'
        while marker in text:
            counter+=1; marker=f'ZXQ{counter}QXZ'
        counter+=1
        marked+=text[end:start]+marker
        replacements.append((marker,target)); end=stop
    marked+=text[end:]
    try: output=translate(marked,source)
    except RuntimeError: output=''
    found=[]
    for marker,target in replacements:
        pattern=r'\s*'.join(map(re.escape,marker))
        matches=list(re.finditer(pattern,output,re.I))
        if len(matches)!=1: break
        found.append((matches[0].start(),matches[0].end(),target))
    else:
        # Work right-to-left so restoring a term never changes another offset.
        for start,stop,target in sorted(found,reverse=True):
            output=output[:start]+target+correct_particle(output[stop:],target)
        if not re.search(r'ZXQ\s*\d+\s*QXZ',output,re.I): return output
    # Some models damage/drop markers. A verified split fallback preserves all
    # source spans and required terms rather than showing broken placeholders.
    parts=[]; end=0
    for start,stop,target in spans:
        segment=text[end:start]
        if segment.strip(): parts.append(translate(segment,source) if re.search(r'\w',segment) else segment)
        parts.append(target); end=stop
    if text[end:].strip():
        segment=text[end:]
        parts.append(translate(segment,source) if re.search(r'\w',segment) else segment)
    return ' '.join(parts)
