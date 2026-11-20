# Contributing to Data for AI

Thanks for helping make these lessons better. Small, focused fixes are the most useful.

## Good first contributions

- A typo or an unclear sentence in a lesson README
- A step that no longer matches the current product or library version
- A broken link, or a script that fails on a fresh install

## How to contribute

1. Open an [issue](https://github.com/aniket-work/data-for-ai/issues) first for anything bigger than a typo. Name the folder and the step.
2. Fork the repo and create a branch.
3. Keep each pull request to **one folder** and one topic.
4. If you change code, run the folder's steps from a clean virtual environment and say what you tested.
5. Keep item names (`IoTEventhouse`, `Telemetry`, `SensorReadings` and so on) as they are, so the folder still matches its video.

## Never commit private details

Do not add passwords, API keys, connection strings, workspace or tenant names or IDs, email addresses, or screenshots that show any of these. The `.gitignore` already blocks common files such as `.env` and `credentials.json`.

## Style

- Plain, short sentences. Explain a term the first time it appears.
- Say clearly when code or a file format was written for the lesson rather than being a product feature or a standard.
- Diagrams go in the folder's `diagrams/` directory, ideally with their source.

## License

By contributing, you agree that your contribution is released under the [MIT License](LICENSE).
