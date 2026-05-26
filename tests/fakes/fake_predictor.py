"""Fake StockPredictorPort implementation for testing."""


class FakePredictor:
    def __init__(self, predictions: list[float] | None = None) -> None:
        self._predictions = predictions or [0.02]
        self.fit_calls: list[tuple[int, int]] = []
        self.predict_calls: list[int] = []

    def fit(self, features: list[dict[str, float]], targets: list[float]) -> None:
        self.fit_calls.append((len(features), len(features[0]) if features else 0))

    def predict(self, features: list[dict[str, float]]) -> list[float]:
        n = len(features)
        self.predict_calls.append(n)
        if len(self._predictions) >= n:
            return self._predictions[:n]
        return self._predictions * n

    def save_model(self, path: str) -> None:
        pass

    def load_model(self, path: str) -> None:
        pass
