import numpy as np
# quarter-car: sprung m_s, unsprung m_u, suspension k_s,c_s, tyre k_t. Assumed typical passenger car values (NOT calibrated).
ms,mu,ks,cs,kt=400.,40.,22000.,1500.,200000.
def road(x,h,L,kind):
    if x<0 or x>L: return 0.0
    u=x/L
    if kind=="round": return h*np.sin(np.pi*u)           # circular-ish hump
    # table: 1/6 ramp up, flat, 1/6 ramp down
    r=L/6
    return h*min(1,x/r,(L-x)/r)
def run(v,h,L,kind,dt=1e-4):
    T=(L+3)/v+1.0; n=int(T/dt)
    zs=vs=zu=vu=0.0; amax=0.0; zmax=0.0; a_hist=[]
    for i in range(n):
        t=i*dt; x=v*t-1.0*v*0.5  # start approach
        x=v*t-2.0
        zr=road(x,h,L,kind)
        Fs=ks*(zu-zs)+cs*(vu-vs); Ft=kt*(zr-zu)
        a_s=Fs/ms; a_u=(-Fs+Ft)/mu
        vs+=a_s*dt; zs+=vs*dt; vu+=a_u*dt; zu+=vu*dt
        a_hist.append(a_s); amax=max(amax,abs(a_s)); zmax=max(zmax,abs(zs))
    return amax/9.81, zmax*100
for v_kmh in (15,20,30):
    v=v_kmh/3.6
    print(f"-- {v_kmh} km/h, bump height 7.5 cm")
    for name,L,kind in (("short round 0.9 m",0.9,"round"),("hump 3.7 m",3.7,"round"),("table 6.7 m",6.7,"table")):
        g,z=run(v,0.075,L,kind)
        print(f"{name:20s} body peak accel {g:5.2f} g, body peak rise {z:5.1f} cm")
