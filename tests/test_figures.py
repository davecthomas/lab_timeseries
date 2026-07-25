import pandas as pd

from lab_timeseries_grapher.data import MetricSeries
from lab_timeseries_grapher.figures import filter_window, make_figure


def make_series(values, band=(2.0, 8.0)):
    dates = pd.date_range("2023-01-01", periods=len(values), freq="MS")
    return MetricSeries(
        name="Test",
        dates=list(dates),
        values=values,
        display_values=[str(v) for v in values],
        band=band,
        units="mg/dL",
        panel="",
    )


class TestFilterWindow:
    def test_no_cutoff_keeps_all(self):
        s = make_series([1.0, 2.0, 3.0])
        assert filter_window(s, None) == [0, 1, 2]

    def test_cutoff_drops_older_points(self):
        s = make_series([1.0, 2.0, 3.0])
        assert filter_window(s, pd.Timestamp("2023-02-15")) == [2]


class TestMakeFigure:
    def test_band_rendered_as_shape(self):
        fig = make_figure(make_series([5.0]))
        assert len(fig.layout.shapes) == 1
        assert fig.layout.shapes[0].y0 == 2.0
        assert fig.layout.shapes[0].y1 == 8.0

    def test_no_shape_without_band(self):
        fig = make_figure(make_series([5.0], band=None))
        assert len(fig.layout.shapes) == 0

    def test_out_of_range_gets_flag_trace(self):
        fig = make_figure(make_series([1.0, 5.0, 9.0]))
        assert len(fig.data) == 2
        flags = fig.data[1]
        assert list(flags.x) == [pd.Timestamp("2023-01-01"), pd.Timestamp("2023-03-01")]
        assert list(flags.marker.symbol) == ["triangle-down", "triangle-up"]

    def test_in_range_has_single_trace(self):
        fig = make_figure(make_series([5.0, 6.0]))
        assert len(fig.data) == 1

    def test_units_on_y_axis(self):
        fig = make_figure(make_series([5.0]))
        assert fig.layout.yaxis.title.text == "mg/dL"

    def test_cutoff_filters_points(self):
        fig = make_figure(make_series([1.0, 5.0, 9.0]), cutoff=pd.Timestamp("2023-02-15"))
        assert list(fig.data[0].y) == [9.0]

    def test_single_point_pads_x_axis(self):
        fig = make_figure(make_series([5.0]))
        lo, hi = fig.layout.xaxis.range
        assert pd.Timestamp(lo) == pd.Timestamp("2022-07-01")
        assert pd.Timestamp(hi) == pd.Timestamp("2023-07-01")

    def test_multi_point_keeps_auto_x_axis(self):
        fig = make_figure(make_series([5.0, 6.0]))
        assert fig.layout.xaxis.range is None
