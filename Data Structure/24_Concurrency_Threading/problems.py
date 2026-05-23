"""24 — Concurrency & Threading — Problems | 8 problems"""
import threading, time, collections

# P01. Print in Order [Easy][LC 1114]
class Foo:
    def __init__(self): self.s2=threading.Semaphore(0); self.s3=threading.Semaphore(0)
    def first(self,f): f(); self.s2.release()
    def second(self,f): self.s2.acquire(); f(); self.s3.release()
    def third(self,f): self.s3.acquire(); f()
foo=Foo(); res=[]
ts=[threading.Thread(target=foo.first,args=[lambda:res.append(1)]),
    threading.Thread(target=foo.second,args=[lambda:res.append(2)]),
    threading.Thread(target=foo.third,args=[lambda:res.append(3)])]
[t.start() for t in ts]; [t.join() for t in ts]
print("P01:",res)  # [1,2,3]

# P02. Print FooBar Alternately [Medium][LC 1115]
class FooBar:
    def __init__(self,n): self.n=n; self.fs=threading.Semaphore(1); self.bs=threading.Semaphore(0)
    def foo(self,f):
        for _ in range(self.n): self.fs.acquire(); f(); self.bs.release()
    def bar(self,f):
        for _ in range(self.n): self.bs.acquire(); f(); self.fs.release()
fb=FooBar(3); r=[]
ts=[threading.Thread(target=fb.foo,args=[lambda:r.append("foo")]),
    threading.Thread(target=fb.bar,args=[lambda:r.append("bar")])]
[t.start() for t in ts]; [t.join() for t in ts]
print("P02:","".join(r))  # foobarfoobarfoobar

# P03. Print Zero Even Odd [Medium][LC 1116]
class ZeroEvenOdd:
    def __init__(self,n):
        self.n=n
        self.zs=threading.Semaphore(1)
        self.es=threading.Semaphore(0)
        self.os=threading.Semaphore(0)
    def zero(self,pz):
        for i in range(1,self.n+1):
            self.zs.acquire(); pz(0)
            (self.os if i%2 else self.es).release()
    def even(self,pe):
        for i in range(2,self.n+1,2):
            self.es.acquire(); pe(i); self.zs.release()
    def odd(self,po):
        for i in range(1,self.n+1,2):
            self.os.acquire(); po(i); self.zs.release()
zeo=ZeroEvenOdd(5); r=[]
ts=[threading.Thread(target=zeo.zero,args=[lambda x:r.append(str(x))]),
    threading.Thread(target=zeo.even,args=[lambda x:r.append(str(x))]),
    threading.Thread(target=zeo.odd, args=[lambda x:r.append(str(x))])]
[t.start() for t in ts]; [t.join() for t in ts]
print("P03:","".join(r))  # 0102030405

# P04. H2O [Medium][LC 1117]
class H2O:
    def __init__(self):
        self.h=threading.Semaphore(2); self.o=threading.Semaphore(0)
        self.b=threading.Barrier(3); self.lock=threading.Lock(); self.hc=0
    def hydrogen(self,rH):
        self.h.acquire(); rH()
        with self.lock:
            self.hc+=1
            if self.hc==2: self.hc=0; self.o.release()
        self.b.wait(); self.h.release()
    def oxygen(self,rO):
        self.o.acquire(); rO(); self.b.wait()
h2o=H2O(); r=[]
def H(): h2o.hydrogen(lambda:r.append("H"))
def O(): h2o.oxygen(lambda:r.append("O"))
ts=[threading.Thread(target=H) for _ in range(4)]+[threading.Thread(target=O) for _ in range(2)]
[t.start() for t in ts]; [t.join() for t in ts]
print("P04:","".join(sorted(r)))  # HHHHOO (sorted, valid water)

# P05. Dining Philosophers [Medium][LC 1226]
class DiningPhilosophers:
    def __init__(self):
        self.forks=[threading.Lock() for _ in range(5)]
    def wantsToEat(self,philosopher,pickL,pickR,eat,putL,putR):
        left=philosopher; right=(philosopher+1)%5
        # Always pick lower-indexed fork first to prevent deadlock
        f1,f2=(left,right) if left<right else (right,left)
        with self.forks[f1]:
            with self.forks[f2]:
                pickL(); pickR(); eat(); putL(); putR()
dp=DiningPhilosophers(); r=[]
def phil(i): dp.wantsToEat(i,lambda:None,lambda:None,lambda:r.append(i),lambda:None,lambda:None)
ts=[threading.Thread(target=phil,args=[i]) for i in range(5)]
[t.start() for t in ts]; [t.join() for t in ts]
print("P05: all ate:",sorted(r))  # [0,1,2,3,4]

# P06. Bounded Blocking Queue [Medium][LC 1188]
class BBQ:
    def __init__(self,cap):
        self.q=collections.deque(); self.cap=cap
        self.lock=threading.Lock()
        self.nf=threading.Condition(self.lock)
        self.ne=threading.Condition(self.lock)
    def enqueue(self,v):
        with self.nf:
            while len(self.q)>=self.cap: self.nf.wait()
            self.q.append(v); self.ne.notify()
    def dequeue(self):
        with self.ne:
            while not self.q: self.ne.wait()
            v=self.q.popleft(); self.nf.notify(); return v
    def size(self): return len(self.q)
bbq=BBQ(3); vals=[]
def prod(): [bbq.enqueue(i) for i in range(6)]
def cons(): [vals.append(bbq.dequeue()) for _ in range(6)]
t1=threading.Thread(target=prod); t2=threading.Thread(target=cons)
t1.start();t2.start();t1.join();t2.join()
print("P06 consumed:",sorted(vals))  # [0,1,2,3,4,5]

# P07. Traffic Light Controlled Intersection [Medium][LC 1279]
class TrafficLight:
    def __init__(self): self.lock=threading.Lock(); self.green="A"
    def carArrived(self,carId,roadId,direction,turnGreen,crossCar):
        with self.lock:
            if self.green!=chr(64+roadId): turnGreen(); self.green=chr(64+roadId)
            crossCar()
tl=TrafficLight(); r=[]
def car(cid,rid,d): tl.carArrived(cid,rid,d,lambda:r.append(f"green{rid}"),lambda:r.append(f"cross{cid}"))
ts=[threading.Thread(target=car,args=[1,1,1]),threading.Thread(target=car,args=[2,1,0]),threading.Thread(target=car,args=[3,2,1])]
[t.start() for t in ts]; [t.join() for t in ts]
print("P07:",r)

# P08. Web Crawler Multithreaded [Medium][LC 1242]
from urllib.parse import urlparse
class Solution1242:
    def crawl(self,startUrl,htmlParser):
        hostname=urlparse(startUrl).netloc
        visited={startUrl}; lock=threading.Lock()
        queue=[startUrl]
        while queue:
            futures=[]
            for url in queue:
                t=threading.Thread(target=self._fetch,args=[url,hostname,htmlParser,visited,lock,futures])
                t.start(); t.join()
            queue=futures
        return list(visited)
    def _fetch(self,url,host,parser,visited,lock,out):
        for link in parser.getUrls(url):
            if urlparse(link).netloc==host:
                with lock:
                    if link not in visited:
                        visited.add(link); out.append(link)

"""
COMPLEXITY SUMMARY:
Print in Order          O(1)  per call  Semaphore(0) signaling
FooBar Alternately      O(n)            Two semaphores ping-pong
Zero Even Odd           O(n)            Three semaphores
H2O                     O(n)            Semaphore + Barrier
Dining Philosophers     O(1)  per eat   Ordered lock acquisition
Bounded Queue           O(1)  amortized Condition variable
Traffic Light           O(1)  per car   Mutex
Web Crawler             O(V+E)          Thread pool + visited set
"""
