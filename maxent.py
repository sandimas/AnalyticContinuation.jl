"""
references:
https://doi.org/10.1016/0370-1573(95)00074-7
https://www.cond-mat.de/events/correl12/manuscripts/jarrell.pdf
https://doi.org/10.1103/PhysRevE.94.023303
"""
import numpy as np
import scipy
from scipy.interpolate import CubicSpline
import scipy.stats
import matplotlib.pyplot as plt


def calc_A(G, K, m, als=np.logspace(9, 1, 1+20*(9-1)), plot=False, useBT=False):
    """
    solve G = K*A for A, where A is normalized to A.sum() ~ 1

    G: binned data with shape (nbin, ntau)
    K: kernel with shape (ntau, nw)
    m: default model function. shape is (nw,)
    als: list of alphas
    plot: loglog plot of chi2 vs. alpha
    """
    # miscellaneous settings
    W_ratio_max = 1e8
    svd_threshold = 1e-12  # drop singular vals if < max singular val * this

    # estimate parameters of multivariate Gaussian distribution from G
    nbin = G.shape[0]
    Gavg = G.mean(0)
    # print(np.shape(Gavg))
    # print(Gavg)
    # calculate unitary matrix for diagonalizing covariance matrix
    # sigma2, Uc = np.linalg.eigh(np.cov(G.T) / nbin)
    # Uc = Uc.T
    # W = 1.0/sigma2
    # equivalent to above, using svd
    sigma, Uc = np.linalg.svd(G - Gavg, False)[1:]
    # print(np.shape(sigma),sigma,"sigma")
    # print(np.shape(Uc),Uc,"Uc")
    W = (nbin*(nbin-1)) / (sigma * sigma)
    # print(np.shape(W),W)
    # cap W in case covariance matrix is nearly singular
    W_cap = W_ratio_max*W.min()
    # print(W_cap)
    n_large = np.sum(W.max() > W_cap)
    if W.max() > W_cap:
        print(f"clipping {n_large} W values to W.min()*{W_ratio_max}")
        W[W > W_cap] = W_cap
    # print(np.shape(Gavg),Gavg,"gavg")
    # rotate K and Gavg
    # print(np.shape(K),K,"K")
    Kp = np.dot(Uc, K)
    # print(np.shape(Kp),Kp,"Kp\n\n")
    Gavgp = np.dot(Uc, Gavg)
    # print(np.shape(Gavgp),Gavgp,"Gavgp")
    # svd of kernel: K = V Sigma U.T
    V, Sigma, U = np.linalg.svd(Kp, False)
    # drop singular values less than threshold
    mask = (Sigma/Sigma.max() >= svd_threshold)
    # print(np.shape(mask),mask,"mask")
    # pre-calculate some stuff
    U = U.T[:, mask]
    SigmaVT = (V[:, mask] * Sigma[mask]).T
    # print(SigmaVT,"SigmaVT")
    # print(np.shape(W),W,"W")
    garbage = SigmaVT * W
    # print(np.shape(garbage),garbage,"garbage")
    M = np.dot(SigmaVT * W, SigmaVT.T)
    # print(np.shape(M),M,"M")
    precalc = (U, SigmaVT, M)

    # if specified alpha
    if np.isscalar(als):
        return calc_A_al(Gavgp, W, Kp, m, als, precalc)[0]
    # print(als.shape,"als")
    us = np.zeros((als.shape[0], M.shape[0]))
    chi2s = np.zeros_like(als)
    # print(chi2s.shape,"chi")
    lnPs = np.zeros_like(als)
    dlnPs = np.zeros_like(als)

    for i, al in enumerate(als):
        us[i], chi2s[i], lnPs[i], dlnPs[i] = calc_A_al(Gavgp, W, Kp, m, al, precalc, us[i-1])[1:]
    # print(us,"us")
    # print(chi2s[0:3],"chi2s")

    order = als.argsort()
    #BT
    # print(np.log(als[order]),"xx")
    fit = CubicSpline(np.log(als[order]), np.log(chi2s[order]))
    # print(fit(10.0),"fit")
    # print(fit.roots(extrapolate=False))
    # print(fit(np.log(als[order]), 2),"test")
    k = fit(np.log(als), 2)/(1 + fit(np.log(als), 1)**2)**1.5
    # print(k,"K")
    i = k.argmax()
    # print(i,k[i],"k")
    # A = m * np.exp(np.dot(U, us[i, :]))

    #classic
    fit = CubicSpline(np.log(als[order]), dlnPs[order])
    roots = fit.roots(extrapolate=False)
    print(roots,"roots")
    if useBT or len(roots) == 0:
        if not useBT:
            print("maximum of P(alpha) outside range. defaulting to BT.")
        al = als[i]
        chi2 = chi2s[i]
        print(np.shape(m),np.shape(np.exp(np.dot(U, us[i, :]))),(np.dot(U, us[i, :])))
        A = m * np.exp(np.dot(U, us[i, :]))
        print(A,"A")
    else:
        al = np.exp(fit.roots(extrapolate=False)[0])
        A, _unused, chi2 = calc_A_al(Gavgp, W, Kp, m, al, precalc)[:3]

    dof = len(W) - n_large
    print(f"alpha={al:.3f}\tchi2/dof={chi2/dof:.3f}\tA.sum()={A.sum():6f}")

    if plot:
        c2lo, c2hi = scipy.stats.chi2.interval(0.95, dof)
        f, ax1 = plt.subplots()
        ax1.plot([als[i], als[i]], [chi2s.min(), chi2s.max()], 'b', lw=1)
        ax1.plot([als.min(), als.max()], [dof, dof], 'k', lw=1)
        ax1.plot([als.min(), als.max()], [c2lo, c2lo], 'k--', lw=1)
        ax1.plot([als.min(), als.max()], [c2hi, c2hi], 'k--', lw=1)
        ax1.plot(als, chi2s, 'b.', ms=3)
        ax1.set_xscale("log")
        ax1.set_yscale("log")
        ax1.set_xlabel(r"$\alpha$")
        ax1.set_ylabel(r"$\chi^2$")
        ax2 = ax1.twinx()
        ax2.plot(als, np.exp(lnPs), 'g.', ms=3)
        ax2.plot([al, al], [0, np.exp(lnPs.max())], 'g', lw=1)
        ax2.set_ylabel(r"$P(\alpha)$")
        plt.show()

    return A


def _Q(A, G, W, K, m, al):
    S = (A - m - scipy.special.xlogy(A, A/m)).sum()
    # print(S)
    KAG = np.dot(K, A) - G
    # print(KAG,"KAG")
    chi2 = np.dot(KAG*KAG, W)
    # print(chi2,"chi2")
    return al*S - 0.5*chi2, S, chi2


def calc_A_al(G, W, K, m, al, precalc=None, u_init=None):
    """maximizes Q for a given alpha = al using Bryan's algorithm"""
    svd_threshold = 1e-12  # drop singular vals if < max singular val * this
    # solver settings
    mu_multiplier = 2.0  # increase/decrease mu by multiplying/dividing by this
    mu_min, mu_max = al/4.0, al*1e100  # range of nonzero mu
    step_max_accept = 0.5  # maximum size of an accepted step
    step_drop_mu = 0.125  # decrease mu if step_size < this
    dQ_threshold = 1e-10
    max_small_dQ = 7  # stop if dQ/Q < dQ_threshold this many times in a row
    max_iter = 1234  # max num of iterations if above condition not met

    if precalc is None:
        # svd of kernel: K = V Sigma U.T
        V, Sigma, U = np.linalg.svd(K, False)
        # drop singular values less than threshold
        mask = (Sigma/Sigma.max() >= svd_threshold)
        # pre-calculate some stuff
        U = U.T[:, mask]
        SigmaVT = (V[:, mask] * Sigma[mask]).T
        M = np.dot(SigmaVT * W, SigmaVT.T)
    else:
        U, SigmaVT, M = precalc

    # initial state
    u = u_init if u_init is not None else np.zeros(M.shape[0])
    mu = al

    I = np.identity(M.shape[0])
    # print(u.shape,U.shape,m.shape)
    A = m * np.exp(np.dot(U, u))
    # print(A.shape,A,"A")
    # print(np.dot(SigmaVT, (np.dot(K, A) - G) * W),"dot\n\n\n")
    f = al*u + np.dot(SigmaVT, (np.dot(K, A) - G) * W)
    # print(f.shape,f,"f")
    # print(U.shape,A.shape,"shapes")
    T = np.dot(U.T * A, U)
    MT = np.dot(M, T)
    Q_old, S, chi2 = _Q(A, G, W, K, m, al)
    
    # search
    small_dQ = 0
    for i in range(max_iter):
        du = np.linalg.solve((al + mu)*I + MT, -f)
        # print(du)
        
        step_size = np.dot(np.dot(du, T), du)
        # print(step_size,"step")
        
        A = m * np.exp(np.dot(U, u + du))
        # print(A,"A\n")
        
        Q_new, S, chi2 = _Q(A, G, W, K, m, al)
        Q_ratio = Q_new/Q_old
        # print(Q_ratio)
        # quit()
        if step_size < step_max_accept and Q_ratio < 1000:
            u += du
            if np.abs(Q_ratio - 1.0) < dQ_threshold:
                small_dQ += 1
                if small_dQ == max_small_dQ:
                    break
            else:
                small_dQ = 0
            if step_size < step_drop_mu:
                mu = mu/mu_multiplier if mu > mu_min else 0.0
            f = al*u + np.dot(SigmaVT, (np.dot(K, A) - G) * W)
            T = np.dot(U.T * A, U)
            MT = np.dot(M, T)
            Q_old = Q_new
        else:
            mu = np.clip(mu*mu_multiplier, mu_min, mu_max)
        x=0
    else:
        x=1
        print(f"alpha={al}: reached max iterations {max_iter}. solver probably failed.")
    # quit()
    # calculate something proportional to ln P(alpha|G,m)
    # print(np.sqrt(W[:, None])*K,"sqrt w *k")
    Z = np.sqrt(W[:, None])*K*np.sqrt(A)
    # print(Z.shape,"z")
    
    lam = np.linalg.svd(Z, False)[1]**2
    # print(lam.shape,lam,"lam")
    lnP = 0.5*np.log(al/(al + lam)).sum() + Q_new
    # print(lnP,"lnp")
    dlnP = np.sum(lam/(al + lam)) / (2*al) + (A - m - scipy.special.xlogy(A, A/m)).sum()
    # print(dlnP,"dlnP")
    # print(u,"u")
    # quit()
    if x == 1: print(dlnP)
    return A, u, chi2, lnP, dlnP


def gen_grid(nw, x_min, x_max, w_x):
    """
    generate grid with nw points scaled by the function w_x.

    w[i] = w_x((i+0.5)/nw * (x_max-x_min) + x_min)
    dw[i] = w_x((i+1)/nw * (x_max-x_min) + x_min) -
            w_x(i/nw * (x_max-x_min) + x_min)

    returns w, dw
    """
    x_all = np.linspace(x_min, x_max, 2*nw+1)
    w_all = np.apply_along_axis(w_x, 0, x_all)
    return w_all[1::2], np.abs(np.diff(w_all[::2]))


def model_flat(dw):
    return dw/dw.sum()


def kernel_f(beta, tau, w):
    """fermionic kernel: K(tau, w) = exp(-tau*w)/(1+exp(-beta*w))"""
    return np.exp(-tau[:]*w)/(1. + np.exp(-beta*w))


def kernel_b(beta, tau, w, sym=True):
    """bosonic kernel: K(tau, w) = w*exp(-tau*w)/(1-exp(-beta*w))"""
    if sym:
        return w*(np.exp(-tau[:, None]*w) + np.exp(-(beta-tau)[:, None]*w)) \
                / (1. - np.exp(-beta*w))
    else:
        return w*np.exp(-tau[:, None]*w)/(1. - np.exp(-beta*w))


print("hello world")

beta = 1.0
dtau = 3
taus = np.array([1./3.,2.0/3.0,1.0])
# np.reshape(taus,(3,1))
# print(taus.shape)
nw=4
omegas = np.array([-1.0,0.0,1.0,2])
print(omegas[0])
nbin=2
G=np.array([[0.2,0.1,0.3],[0.01,0.2,0.3]])
K=np.zeros((dtau,nw))

for w in range(0,nw):
  K[:,w] = kernel_f(beta,taus,omegas[w])
model = np.array([.1,.5,.3,.1])
A = calc_A(G,K,model,plot=False)