# Lint as: python3
# Copyright 2019 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


"""Tests for vanilla_price."""

import functools

from absl.testing import parameterized

import numpy as np
import tensorflow.compat.v2 as tf
import tensorflow_probability as tfp

import tf_quant_finance as tff
from tensorflow.python.framework import test_util  # pylint: disable=g-direct-tensorflow-import


@test_util.run_all_in_graph_and_eager_modes
class VanillaPrice(parameterized.TestCase, tf.test.TestCase):
  """Tests for methods for the vanilla pricing module."""

  def test_option_prices(self):
    """Tests that the BS prices are correct."""
    forwards = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    strikes = np.array([3.0, 3.0, 3.0, 3.0, 3.0])
    volatilities = np.array([0.0001, 102.0, 2.0, 0.1, 0.4])
    expiries = 1.0
    computed_prices = self.evaluate(
        tff.black_scholes.option_price(
            volatilities=volatilities,
            strikes=strikes,
            expiries=expiries,
            forwards=forwards))
    expected_prices = np.array(
        [0.0, 2.0, 2.0480684764112578, 1.0002029716043364, 2.0730313058959933])
    self.assertArrayNear(expected_prices, computed_prices, 1e-10)

  def test_price_zero_vol(self):
    """Tests that zero volatility is handled correctly."""
    # If the volatility is zero, the option's value should be correct.
    forwards = np.array([1.0, 1.0, 1.0, 1.0])
    strikes = np.array([1.1, 0.9, 1.1, 0.9])
    volatilities = np.array([0.0, 0.0, 0.0, 0.0])
    expiries = 1.0
    is_call_options = np.array([True, True, False, False])
    expected_prices = np.array([0.0, 0.1, 0.1, 0.0])
    computed_prices = self.evaluate(
        tff.black_scholes.option_price(
            volatilities=volatilities,
            strikes=strikes,
            expiries=expiries,
            forwards=forwards,
            is_call_options=is_call_options))
    self.assertArrayNear(expected_prices, computed_prices, 1e-10)

  def test_price_zero_expiry(self):
    """Tests that zero expiry is correctly handled."""
    # If the expiry is zero, the option's value should be correct.
    forwards = np.array([1.0, 1.0, 1.0, 1.0])
    strikes = np.array([1.1, 0.9, 1.1, 0.9])
    volatilities = np.array([0.1, 0.2, 0.5, 0.9])
    expiries = 0.0
    is_call_options = np.array([True, True, False, False])
    expected_prices = np.array([0.0, 0.1, 0.1, 0.0])
    computed_prices = self.evaluate(
        tff.black_scholes.option_price(
            volatilities=volatilities,
            strikes=strikes,
            expiries=expiries,
            forwards=forwards,
            is_call_options=is_call_options))
    self.assertArrayNear(expected_prices, computed_prices, 1e-10)

  def test_price_long_expiry_calls(self):
    """Tests that very long expiry call option behaves like the asset."""
    forwards = np.array([1.0, 1.0, 1.0, 1.0])
    strikes = np.array([1.1, 0.9, 1.1, 0.9])
    volatilities = np.array([0.1, 0.2, 0.5, 0.9])
    expiries = 1e10
    expected_prices = forwards
    computed_prices = self.evaluate(
        tff.black_scholes.option_price(
            volatilities=volatilities,
            strikes=strikes,
            expiries=expiries,
            forwards=forwards))
    self.assertArrayNear(expected_prices, computed_prices, 1e-10)

  def test_price_long_expiry_puts(self):
    """Tests that very long expiry put option is worth the strike."""
    forwards = np.array([1.0, 1.0, 1.0, 1.0])
    strikes = np.array([0.1, 10.0, 3.0, 0.0001])
    volatilities = np.array([0.1, 0.2, 0.5, 0.9])
    expiries = 1e10
    expected_prices = strikes
    computed_prices = self.evaluate(
        tff.black_scholes.option_price(
            volatilities=volatilities,
            strikes=strikes,
            expiries=expiries,
            forwards=forwards,
            is_call_options=False))
    self.assertArrayNear(expected_prices, computed_prices, 1e-10)

  def test_price_vol_and_expiry_scaling(self):
    """Tests that the price is invariant under vol->k vol, T->T/k**2."""
    np.random.seed(1234)
    n = 20
    forwards = np.exp(np.random.randn(n))
    volatilities = np.exp(np.random.randn(n) / 2)
    strikes = np.exp(np.random.randn(n))
    expiries = np.exp(np.random.randn(n))
    scaling = 5.0
    base_prices = self.evaluate(
        tff.black_scholes.option_price(
            volatilities=volatilities,
            strikes=strikes,
            expiries=expiries,
            forwards=forwards))
    scaled_prices = self.evaluate(
        tff.black_scholes.option_price(
            volatilities=volatilities * scaling,
            strikes=strikes,
            expiries=expiries / scaling / scaling,
            forwards=forwards))
    self.assertArrayNear(base_prices, scaled_prices, 1e-10)

  @parameterized.named_parameters(
      {
          'testcase_name': 'SinglePrecision',
          'dtype': np.float32
      }, {
          'testcase_name': 'DoublePrecision',
          'dtype': np.float64},
  )
  def test_option_prices_detailed_discount(self, dtype):
    """Tests the prices with discount_rates and cost_of_carries are."""
    spots = np.array([80.0, 90.0, 100.0, 110.0, 120.0] * 2)
    strikes = np.array([100.0] * 10)
    discount_rates = 0.08
    volatilities = 0.2
    expiries = 0.25

    is_call_options = np.array([True] * 5 + [False] * 5)
    cost_of_carries = -0.04
    computed_prices = self.evaluate(
        tff.black_scholes.option_price(
            volatilities=volatilities,
            strikes=strikes,
            expiries=expiries,
            spots=spots,
            discount_rates=discount_rates,
            cost_of_carries=cost_of_carries,
            is_call_options=is_call_options,
            dtype=dtype))
    expected_prices = np.array([0.03, 0.57, 3.42, 9.85, 18.62, 20.41, 11.25,
                                4.40, 1.12, 0.18])
    self.assertArrayNear(expected_prices, computed_prices, 5e-3)

  def test_binary_prices(self):
    """Tests that the BS binary option prices are correct."""
    forwards = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    strikes = np.array([3.0, 3.0, 3.0, 3.0, 3.0])
    volatilities = np.array([0.0001, 102.0, 2.0, 0.1, 0.4])
    expiries = 1.0
    computed_prices = self.evaluate(
        tff.black_scholes.binary_price(
            volatilities=volatilities,
            strikes=strikes,
            expiries=expiries,
            forwards=forwards))
    expected_prices = np.array([0.0, 0.0, 0.15865525, 0.99764937, 0.85927418])
    self.assertArrayNear(expected_prices, computed_prices, 1e-8)

  def test_binary_prices_bulk(self):
    """Tests unit of cash binary option pricing over a wide range of settings.

    Uses the fact that if the underlying follows a geometric brownian motion
    then, given the mean on the exponential scale and the variance on the log
    scale, the mean on the log scale is known. In particular for underlying S
    with forward price F, strike K, volatility sig, and expiry T:

    log(S) ~ N(log(F) - sig^2 T, sig^2 T)

    The price of the binary call option is the discounted probability that S
    will be greater than K at expiry (and for a put option, less than K). Since
    quantiles are preserved under monotonic transformations we can find this
    probability on the log scale. This provides an alternate calculation for the
    same price which we can use to corroborate the standard method.
    """
    np.random.seed(321)
    num_examples = 1000
    forwards = np.exp(np.random.normal(size=num_examples))
    strikes = np.exp(np.random.normal(size=num_examples))
    volatilities = np.exp(np.random.normal(size=num_examples))
    expiries = np.random.gamma(shape=1.0, scale=1.0, size=num_examples)
    log_scale = np.sqrt(expiries) * volatilities
    log_loc = np.log(forwards) - 0.5 * log_scale**2
    call_options = np.random.binomial(n=1, p=0.5, size=num_examples)
    discount_factors = np.random.beta(a=1.0, b=1.0, size=num_examples)

    cdf_values = self.evaluate(
        tfp.distributions.Normal(loc=log_loc,
                                 scale=log_scale).cdf(np.log(strikes)))

    expected_prices = discount_factors * (
        call_options + ((-1.0)**call_options) * cdf_values)

    is_call_options = np.array(call_options, dtype=np.bool)
    computed_prices = self.evaluate(
        tff.black_scholes.binary_price(
            volatilities=volatilities,
            strikes=strikes,
            expiries=expiries,
            forwards=forwards,
            is_call_options=is_call_options,
            discount_factors=discount_factors))
    self.assertArrayNear(expected_prices, computed_prices, 1e-10)

  def test_binary_vanilla_call_consistency(self):
    r"""Tests code consistency through relationship of binary and vanilla prices.

    With forward F, strike K, discount rate r, and expiry T, a vanilla call
    option should have price CV:

    $$ VC(K) = e^{-rT}( N(d_1)F - N(d_2)K ) $$

    A unit of cash paying binary call option should have price BC:

    $$ BC(K) = e^{-rT} N(d_2) $$

    Where d_1 and d_2 are standard Black-Scholes quanitities and depend on K
    through the ratio F/K. Hence for a small increment e:

    $$ (VC(K + e) - Vc(K))/e \approx -N(d_2)e^{-rT} = -BC(K + e) $$

    Similarly, for a vanilla put:

    $$ (VP(K + e) - VP(K))/e \approx N(-d_2)e^{-rT} = BP(K + e) $$

    This enables a test for consistency of pricing between vanilla and binary
    options prices.
    """
    np.random.seed(135)
    num_examples = 1000
    forwards = np.exp(np.random.normal(size=num_examples))
    strikes_0 = np.exp(np.random.normal(size=num_examples))
    epsilon = 1e-8
    strikes_1 = strikes_0 + epsilon
    volatilities = np.exp(np.random.normal(size=num_examples))
    expiries = np.random.gamma(shape=1.0, scale=1.0, size=num_examples)
    call_options = np.random.binomial(n=1, p=0.5, size=num_examples)
    is_call_options = np.array(call_options, dtype=np.bool)
    discount_factors = np.ones_like(forwards)

    option_prices_0 = self.evaluate(
        tff.black_scholes.option_price(
            volatilities=volatilities,
            strikes=strikes_0,
            expiries=expiries,
            forwards=forwards,
            is_call_options=is_call_options))

    option_prices_1 = self.evaluate(
        tff.black_scholes.option_price(
            volatilities=volatilities,
            strikes=strikes_1,
            expiries=expiries,
            forwards=forwards,
            is_call_options=is_call_options))

    binary_approximation = (-1.0)**call_options * (option_prices_1 -
                                                   option_prices_0) / epsilon

    binary_prices = self.evaluate(
        tff.black_scholes.binary_price(
            volatilities=volatilities,
            strikes=strikes_1,
            expiries=expiries,
            forwards=forwards,
            is_call_options=is_call_options,
            discount_factors=discount_factors))

    self.assertArrayNear(binary_approximation, binary_prices, 1e-6)

  def test_binary_vanilla_consistency_exact(self):
    """Tests that the binary price is the negative gradient of vanilla price.

      The binary call option payoff is 1 when spot > strike and 0 otherwise.
      This payoff is the proportional to the gradient of the payoff of a vanilla
      call option (max(S-K, 0)) with respect to K. This test verifies that this
      relationship is satisfied. A similar relation holds true between vanilla
      puts and binary puts.
    """
    dtype = np.float64
    strikes = tf.constant([1.0, 2.0], dtype=dtype)
    spots = tf.constant([1.5, 1.5], dtype=dtype)
    expiries = tf.constant([2.1, 1.3], dtype=dtype)
    discount_rates = tf.constant([0.03, 0.04], dtype=dtype)
    discount_factors = tf.exp(-discount_rates * expiries)
    is_call_options = tf.constant([True, False])
    volatilities = tf.constant([0.3, 0.4], dtype=dtype)
    actual_binary_price = self.evaluate(
        tff.black_scholes.binary_price(
            volatilities=volatilities,
            strikes=strikes,
            expiries=expiries,
            spots=spots,
            discount_factors=discount_factors,
            is_call_options=is_call_options))
    price_fn = functools.partial(
        tff.black_scholes.option_price,
        volatilities=volatilities,
        spots=spots,
        expiries=expiries,
        discount_rates=discount_rates,
        is_call_options=is_call_options)
    implied_binary_price = tff.math.fwd_gradient(lambda x: price_fn(strikes=x),
                                                 strikes)
    implied_binary_price = self.evaluate(
        tf.where(is_call_options, -implied_binary_price, implied_binary_price))
    self.assertArrayNear(implied_binary_price, actual_binary_price, 1e-10)

  def test_price_barrier_option_1d(self):
    """Function tests barrier option pricing for scalar input"""
    spots = 100.0
    rebates = 3.0
    expiries = 0.5
    discount_rates = 0.08
    b = 0.04
    asset_yield = -(b-discount_rates)
    strikes, barriers, price_true, barriers_type = self.get_test_vals("cdo")
    volatilities = 0.25
    """
    1 -> cdi
    2 -> pdi
    3 -> cui
    4 -> pui
    5 -> cdo
    6 -> pdo
    7 -> cuo
    8 -> puo
    """
    price = tff.black_scholes.barrier_option_price(
        volatilities, strikes, expiries, spots,
        discount_rates, asset_yield, barriers, rebates, barriers_type)
    self.assertAllClose(price, price_true, 10e-3)

  def get_test_vals(self, param):
    """Function returns testing vals for type of option"""
    if param == "cdo":
      return 90, 95, 9.0246, 5
    if param == "cdi":
      return 90, 95, 7.7627, 1
    if param == "cuo":
      return 90, 105, 2.6789, 7
    if param == "cui":
      return 90, 105, 14.1112, 3
    if param == "pdo":
      return 90, 95, 2.2798, 6
    if param == "puo":
      return 90, 105, 3.7760, 8
    if param == "pdi":
      return 90, 95, 2.9586, 2
    if param == "pui":
      return 90, 105, 1.4653, 4

  def test_price_barrier_option_2d(self):
    """Function tests barrier option pricing for vector inputs"""
    spots = [100., 100., 100., 100., 100., 100., 100., 100.]
    rebatess = [3., 3., 3., 3., 3., 3., 3., 3.]
    expiries = [.5, .5, .5, .5, .5, .5, .5, .5]
    discount_discount_ratess = [.08, .08, .08, .08, .08, .08, .08, .08]
    volatilities = [.25, .25, .25, .25, .25, .25, .25, .25]
    strikes = [90., 90., 90., 90., 90., 90., 90., 90.]
    barriers = [95., 95., 105., 105., 95., 105., 95., 105.]
    price_true = [
        9.024, 7.7627, 2.6789, 14.1112, 2.2798, 3.7760, 2.95586, 1.4653]
    barriers_type = [5, 1, 7, 3, 6, 8, 2, 4]
    asset_yield = [.04, .04, .04, .04, .04, .04, .04, .04]
    price = tff.black_scholes.barrier_option_price(
        volatilities, strikes, expiries, spots,
        discount_discount_ratess, asset_yield, barriers, rebatess, barriers_type)
    self.assertAllClose(price, price_true, 10e-3)

if __name__ == '__main__':
  tf.test.main()
