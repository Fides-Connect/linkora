# connectx

A new Flutter project.

## Getting Started

This project is a starting point for a Flutter application.

A few resources to get you started if this is your first Flutter project:

- [Lab: Write your first Flutter app](https://docs.flutter.dev/get-started/codelab)
- [Cookbook: Useful Flutter samples](https://docs.flutter.dev/cookbook)

For help getting started with Flutter development, view the
[online documentation](https://docs.flutter.dev/), which offers tutorials,
samples, guidance on mobile development, and a full API reference.

## Environment Variables

ConnectX supports configuration via a `.env` file.  
This file should be placed in the project root (`/workspaces/flutter-dev-workspace/connectx/.env`) and is used to store sensitive or environment-specific settings.

> **Note:**  
> A `template.env` file is provided in the project root as an example.  
> Copy or rename `template.env` to `.env` and update the values as needed.

### How to use

1. **Create a `.env` file** in the project root if it does not exist.
2. **Add your environment variables** in the format:  
   ```
   VARIABLE_NAME=value
   ```
   Example:
   ```
   API_KEY=your_api_key_here
   BASE_URL=https://api.example.com
   ```

3. **Access variables in your code** using your preferred Dart/Flutter package for environment variables (e.g., `flutter_dotenv`).

### Notes

- The `.env` file is **excluded from version control** via `.gitignore`.  
  Do not commit sensitive information to your repository.
- For production, set environment variables securely on your deployment platform.
