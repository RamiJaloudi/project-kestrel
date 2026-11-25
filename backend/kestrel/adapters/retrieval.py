"""Deterministic ranking over an already-authorized corpus. Never performs authorization."""
import math,re
from collections import Counter

def tokens(text):
    # Keep identifiers/decimal strings intact; case-fold names/tickers without changing numeric magnitude.
    found=re.findall(r"[^\W_]+(?:[./:-][^\W_]+)*",text.casefold(),re.UNICODE)
    return [part for token in found for part in ([token]+token.split('-') if '-' in token and all(p.isalpha() for p in token.split('-')) else [token])]


def bm25(query,texts,k1=1.5,b=0.75):
    q=set(tokens(query));docs=[Counter(tokens(t)) for t in texts];n=len(docs)
    if not n or not q:return []
    lengths=[sum(d.values()) for d in docs];avg=sum(lengths)/n or 1;df={t:sum(t in d for d in docs) for t in q};scores=[]
    for i,d in enumerate(docs):
        score=0.0
        for t in sorted(q):
            f=d[t]
            if f:score+=math.log(1+(n-df[t]+0.5)/(df[t]+0.5))*f*(k1+1)/(f+k1*(1-b+b*lengths[i]/avg))
        if score>0:scores.append((i,score))
    return sorted(scores,key=lambda pair:(-pair[1],pair[0]))


def cosine(a,b):
    if len(a)!=len(b) or not a or any(type(v) not in {int,float} or not math.isfinite(v) for v in [*a,*b]):raise ValueError('Invalid embedding vector')
    left=math.sqrt(sum(v*v for v in a));right=math.sqrt(sum(v*v for v in b))
    if not left or not right or not math.isfinite(left*right):raise ValueError('Invalid embedding norm')
    return sum(x*y for x,y in zip(a,b))/(left*right)


def rrf(rankings,constant=60):
    scores={}
    for ranking in rankings:
        for rank,i in enumerate(ranking,1):scores[i]=scores.get(i,0)+1/(constant+rank)
    return sorted(scores.items(),key=lambda pair:(-pair[1],pair[0]))
