import numpy as np
from scipy import stats

try:
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
except ImportError:
    plt = None

try:
    import seaborn as sns
    sns.set(color_codes=True)
except ImportError:
    sns = None


__all__ = ["two_on_single", "two_on_multiple",
           "signtest", "plot_posterior_sign", "plot_simplex",
           "correlated_t", "plot_posterior_t",
           "LEFT", "ROPE", "RIGHT"]


def requires(module, library):
    def wrapper(f):
        def check_and_call(*args, **kwargs):
            if module is None:
                raise ImportError("'{}' requires library '{}'"
                                  .format(f.__name__, library))
            return f(*args, **kwargs)
        return check_and_call
    return wrapper


def _compute_posterior_t_parameters(x, y=None, runs=1):
    if not int(runs) == runs > 0:
        raise ValueError('Number of runs must be a positive integer')
    if y is not None:
        x = y - x
    n = len(x)
    nfolds = n / runs
    mean = np.mean(x)
    var = np.var(x, ddof=1)
    var *= 1 / n + 1 / (nfolds - 1)  # Nadeau-Bengio's correction
    return mean, var, n - 1


def correlated_t(x, y=None, rope=0, runs=1):
    """
    Compute correlated t-test

    The function uses the Bayesian interpretation of the p-value and returns
    the probabilities the difference are below `-rope`, within `[-rope, rope]`
    and above the `rope`. For details, see `A Bayesian approach for comparing
    cross-validated algorithms on multiple data sets
    <http://link.springer.com/article/10.1007%2Fs10994-015-5486-z>`_,
    G. Corani and A. Benavoli, Mach Learning 2015.

    The test assumes that the classifiers were evaluated using cross
    validation. The number of folds is determined from the length of the vector
    of differences, as `len(diff) / runs`. The variance includes a correction
    for underestimation of variance due to overlapping training sets, as
    described in `Inference for the Generalization Error
    <http://link.springer.com/article/10.1023%2FA%3A1024068626366>`_,
    C. Nadeau and Y. Bengio, Mach Learning 2003.).

    Args:
        x (np.array): a vector of scores for the first model, or differences
        y (np.array): a vector of scores for the second model; if `None`,
            `x` contains differences between the models
        rope (float): the width of the rope (default: 0)
        runs (int): number of repetitions of cross validation (default: 1)

    Returns:
        (p_left, p_rope, p_right), or (p_left, p_right) if rope is 0
    """
    mean, var, df = _compute_posterior_t_parameters(x, y, runs)
    if var == 0:
        return float(mean < rope), float(-rope <= mean <= rope), float(rope < mean)
    greater = stats.t.cdf(mean, df, rope, np.sqrt(var))
    less = 1 - stats.t.cdf(mean, df, -rope, np.sqrt(var))
    if rope == 0:
        return less, greater
    return less, 1 - greater - less, greater


@requires(plt, "matplotlib")
def plot_posterior_t(x, y=None, rope=0.1, runs=1, names=None):
    """
    Plot posterior distribution and rope intervals for correlated t-test

    See documentation for function :obj:`correlated_t` for details.

    Args:
        x (np.array): a vector of scores for the first model, or differences
        y (np.array): a vector of scores for the second model; if `None`,
            `x` contains differences between the models
        rope (float): the width of the rope (default: 0)
        runs (int): number of repetitions of cross validation (default: 1)
        names (pair of str): the names of the two classifiers (default: None,
            no names are shown on the plot)

    Returns:
        matplotlib.pyplot.figure
    """
    if names is not None:
        if y is None:
            raise ValueError("argument 'names' requires separate 'x' and 'y'")
        x_label = "difference ({}: {:.3f}, {}: {:.3f})".format(
            names[0], np.mean(x), names[1], np.mean(y))
    else:
        x_label = "difference"

    fig, ax = plt.subplots()
    ax.grid(True)
    ax.set_xlabel(x_label)
    ax.get_yaxis().set_ticklabels([])
    ax.axvline(x=-rope, color="#ffad2f", linewidth=2, label="rope")
    ax.axvline(x=rope, color="#ffad2f", linewidth=2)

    mean, var, df = _compute_posterior_t_parameters(x, y, runs)
    targs = (df, mean, np.sqrt(var))
    xs = np.linspace(min(stats.t.ppf(0.005, *targs), -1.05 * rope),
                     max(stats.t.ppf(0.995, *targs), 1.05 * rope),
                     100)
    ys = stats.t.pdf(xs, *targs)
    ax.plot(xs, ys, color="#2f56e0", linewidth=2, label="pdf")
    ax.fill_between(xs, ys, np.zeros(100), color="#34ccff")
    ax.legend()
    return fig


LEFT, ROPE, RIGHT = range(3)

def monte_carlo_samples(x, y=None, rope=0, prior=1, nsamples=50000):
    """
    Args:
        x (np.array): a vector of scores for the first model, or differences
        y (np.array): a vector of scores for the second model; if `None`,
            `x` contains differences between the models
        rope (float): the width of the rope (default: 0)
        prior (float or tuple): prior strength, or tuple with strength and
            place (`LEFT`, `ROPE` or `RIGHT`); (default: 1)
        nsamples (int): the number of Monte Carlo samples (default: 50000)

    Returns:
        2-d array with rows corresponding to samples and columns to
        probabilities `[p_left, p_rope, p_right]`
    """
    if isinstance(prior, tuple):
        prior, prior_place = prior
    else:
        prior_place = ROPE
    if prior < 0:
        raise ValueError('Prior strength cannot be negative')
    if not round(nsamples) == nsamples > 0:
        raise ValueError('Number of samples must be a positive integer')
    if rope < 0:
        raise ValueError('Rope width cannot be negative')
    if y is not None:
        x = y - x

    nleft = sum(x < -rope)
    nright = sum(x > rope)
    nrope = len(x) - nleft - nright
    alpha = np.array([nleft, nrope, nright], dtype=float)
    alpha += 0.0001  # for numerical stability
    alpha[prior_place] += prior
    return np.random.dirichlet(alpha, nsamples)  # pylint: disable=no-member


def signtest(x, y=None, rope=0, prior=1, nsamples=50000):
    """
    Args:
        x (np.array): a vector of scores for the first model, or differences
        y (np.array): a vector of scores for the second model; if `None`,
            `x` contains differences between the models
        rope (float): the width of the rope (default: 0)
        prior (float or tuple): prior strength, or tuple with strength and
            place (`LEFT`, `ROPE` or `RIGHT`); (default: 1)
        nsamples (int): the number of Monte Carlo samples (default: 50000)
        verbose (bool): report the computed probabilities (default: False)
        names (pair of str): the names of the two classifiers (default: C1, C2)

    Returns:
        p_left, p_rope, p_right
    """
    samples = monte_carlo_samples(x, y, rope, prior, nsamples)
    winners = np.argmax(samples, axis=1)
    pl, pe, pr = np.bincount(winners, minlength=3) / len(winners)
    if rope == 0:
        return pl, pr
    return pl, pe, pr


@requires(plt, "matplotlib")
def plot_posterior_sign(x, y=None, rope=0, prior=1, nsamples=50000,
                        names=('C1', 'C2')):
    """
    Args:
        x (np.array): a vector of scores for the first model, or differences
        y (np.array): a vector of scores for the second model; if `None`,
            `x` contains differences between the models
        rope (float): the width of the rope (default: 0)
        prior (float or tuple): prior strength, or tuple with strength and
            place (`LEFT`, `ROPE` or `RIGHT`); (default: 1)
        nsamples (int): the number of Monte Carlo samples (default: 50000)
        names (pair of str): the names of the two classifiers (default: C1, C2)

    Returns:
        matplotlib.pyplot.figure
    """
    points = monte_carlo_samples(x, y, rope, prior, nsamples)
    return plot_simplex(points, names)


@requires(plt, "matplotlib")
def plot_simplex(points, names=('C1', 'C2')):
    def _project(points):
        from math import sqrt, sin, cos, pi
        p1, p2, p3 = points.T / sqrt(3)
        x = (p2 - p1) * cos(pi / 6) + 0.5
        y = p3 - (p1 + p2) * sin(pi / 6) + 1 / (2 * sqrt(3))
        return np.vstack((x, y)).T

    winners = np.argmax(points, axis=1)
    pl, pe, pr = np.bincount(winners, minlength=3) / len(winners)

    vert0 = _project(np.array(
        [[0.3333, 0.3333, 0.3333], [0.5, 0.5, 0], [0.5, 0, 0.5], [0, 0.5, 0.5]]))

    fig, ax = plt.subplots()
    ax.set_aspect('equal', 'box')

    # triangle
    ax.add_line(
        Line2D([0, 0.5, 1.0, 0],
               [0, np.sqrt(3) / 2, 0, 0], color='orange'))
    # decision lines
    for i in (1, 2, 3):
        ax.add_line(
            Line2D([vert0[0, 0], vert0[i, 0]],
                   [vert0[0, 1], vert0[i, 1]], color='orange'))

    ax.text(0, -0.04,
            'p({})={:.3f}'.format(names[0], pl),
            horizontalalignment='center', verticalalignment='top')
    ax.text(0.5, np.sqrt(3) / 2,
            'p(rope) = {:.3f}'.format(pe),
            horizontalalignment='center', verticalalignment='bottom')
    ax.text(1, -0.04,
            'p({})={:.3f}'.format(names[1], pr),
            horizontalalignment='center', verticalalignment='top')

    # project and draw points
    tripts = _project(points[:, [0, 2, 1]])
    # pylint: disable=no-member
    plt.hexbin(tripts[:, 0], tripts[:, 1], mincnt=1, cmap=plt.cm.Blues_r)
    # Leave some padding around the triangle for vertex labels
    ax.set_xlim(-0.2, 1.2)
    ax.set_ylim(-0.2, 1.2)
    ax.axis('off')
    return fig

two_on_single = correlated_t
two_on_multiple = signtest
