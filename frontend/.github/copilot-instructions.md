<!-- Workspace-specific custom instructions for GitHub Copilot -->

## Project Overview
This is a React + TypeScript + Vite project with MSAL (Microsoft Authentication Library) integration for authentication. The project is structured for scalability with organized folders for components, hooks, types, and configuration.

## Tech Stack
- React 18
- TypeScript
- Vite (build tool)
- MSAL React (@azure/msal-react)
- MSAL Browser (@azure/msal-browser)

## Project Structure
```
src/
├── components/          # Reusable UI components
├── hooks/              # Custom React hooks
├── types/              # TypeScript type definitions
├── config/             # Configuration files (MSAL, etc.)
├── pages/              # Page components
├── styles/             # CSS/styling files
└── utils/              # Utility functions
```

## Authentication Flow
- Uses MSAL popup authentication
- Environment variables for configuration
- Centralized auth configuration
- Protected routes and components

## Development Guidelines
- Use TypeScript for all files
- Follow React functional component patterns
- Organize code by feature/domain
- Keep configuration separate from components
- Use environment variables for sensitive data

## Completed Setup Steps
✅ Created copilot-instructions.md file
✅ Got project setup information  
🔄 Scaffolding React Vite TypeScript project
⏳ Installing MSAL dependencies
⏳ Creating environment configuration
⏳ Setting up MSAL configuration
⏳ Creating login component
⏳ Organizing project structure
⏳ Testing and documentation