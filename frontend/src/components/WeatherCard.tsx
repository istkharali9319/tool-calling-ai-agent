import type { ToolCall } from "../types";

// Shape of the get_weather tool result (see app/tools/weather_tools.py).
export interface WeatherResult {
  location: { name: string; region: string | null; country: string | null; timezone: string | null };
  current: {
    time: string | null;
    condition: string;
    weather_code: number | null;
    is_day: boolean;
    temperature: number | null;
    feels_like: number | null;
    humidity: number | null;
    wind_speed: number | null;
  };
  daily: {
    date: string;
    condition: string;
    weather_code: number | null;
    temperature_max: number | null;
    temperature_min: number | null;
    precipitation_probability: number | null;
  }[];
  units: { temperature: string; wind_speed: string };
}

/** Successful get_weather results from a reply's tool calls. */
export function weatherResults(calls: ToolCall[]): WeatherResult[] {
  return calls
    .filter((c) => c.name === "get_weather" && c.ok && c.result && typeof c.result === "object")
    .map((c) => c.result as WeatherResult)
    .filter((r) => r.location && r.current);
}

function icon(code: number | null, isDay = true): string {
  if (code === null) return "🌡️";
  if (code === 0) return isDay ? "☀️" : "🌙";
  if (code <= 2) return isDay ? "🌤️" : "☁️";
  if (code === 3) return "☁️";
  if (code === 45 || code === 48) return "🌫️";
  if (code >= 51 && code <= 57) return "🌦️";
  if ((code >= 61 && code <= 67) || (code >= 80 && code <= 82)) return "🌧️";
  if ((code >= 71 && code <= 77) || code === 85 || code === 86) return "🌨️";
  if (code >= 95) return "⛈️";
  return "🌡️";
}

const round = (n: number | null) => (n === null || n === undefined ? "–" : Math.round(n));

function dayLabel(date: string, index: number): string {
  if (index === 0) return "Today";
  // Parse as a local calendar date, not UTC midnight, so the weekday is right everywhere.
  const [y, m, d] = date.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString(undefined, { weekday: "short" });
}

export function WeatherCard({ data }: { data: WeatherResult }) {
  const { location, current, daily, units } = data;
  const place = [location.region, location.country].filter(Boolean).join(", ");

  return (
    <section className="weather" aria-label={`Weather in ${location.name}`}>
      <header className="weather-head">
        <div>
          <h3>{location.name}</h3>
          {place && <p>{place}</p>}
        </div>
        <span className="weather-source">Open-Meteo</span>
      </header>

      <div className="weather-now">
        <span className="weather-icon" aria-hidden>
          {icon(current.weather_code, current.is_day)}
        </span>
        <span className="weather-temp">
          {round(current.temperature)}
          <small>{units.temperature}</small>
        </span>
        <div className="weather-details">
          <strong>{current.condition}</strong>
          <span>
            Feels like {round(current.feels_like)}
            {units.temperature}
          </span>
          <span>
            Humidity {round(current.humidity)}% · Wind {round(current.wind_speed)} {units.wind_speed}
          </span>
        </div>
      </div>

      {daily.length > 0 && (
        <ol className="weather-days">
          {daily.map((day, i) => (
            <li key={day.date} title={day.condition}>
              <span className="weather-day">{dayLabel(day.date, i)}</span>
              <span className="weather-day-icon" aria-label={day.condition}>
                {icon(day.weather_code)}
              </span>
              <span className="weather-range">
                <strong>{round(day.temperature_max)}°</strong> {round(day.temperature_min)}°
              </span>
              {day.precipitation_probability !== null && (
                <span className="weather-rain">💧 {day.precipitation_probability}%</span>
              )}
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
