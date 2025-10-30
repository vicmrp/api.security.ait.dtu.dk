# API Security AIT DTU Frontend

React + TypeScript + Vite application for DTU's API Security tools with Azure AD authentication.

## 🚀 Quick Start

### Prerequisites
- Node.js 18+ 
- npm or yarn
- Azure AD App Registration

### Installation

1. **Clone the repository:**
```bash
git clone <your-repository-url>
cd view.security.ait.dtu.dk
```

2. **Install dependencies:**
```bash
npm install
```

3. **Configure environment variables:**
```bash
cp .env.example .env
```

Edit `.env` with your Azure AD configuration:
- `VITE_MSAL_CLIENT_ID`: Your Azure App Registration Client ID
- `VITE_MSAL_TENANT_ID`: Your Azure Tenant ID  
- `VITE_MSAL_AUTHORITY`: Azure authority URL with your tenant
- `VITE_API_CLIENT_ID`: API Client ID for scope generation

4. **Start development server:**
```bash
npm run dev
```

## 🔒 Security Features

### Azure AD Authentication
- **MSAL Integration**: Uses @azure/msal-react for secure authentication
- **Token Management**: Automatic token refresh and secure storage
- **Scoped Access**: API calls use Bearer token with proper scopes

### Security Tools
- **Breach Check**: Search for compromised accounts
- **Unfamiliar Login Analysis**: Monitor login locations and threats
- **MFA Reset**: Administrative tool for user MFA management
- **World Map Visualization**: Geographic login activity display

## 🏗️ Architecture

### Frontend Security
- **Environment Variables**: Sensitive data in `.env` (never committed)
- **HTTPS Only**: Production deployment should use HTTPS
- **Token Security**: Azure AD tokens stored securely by MSAL
- **CORS Protection**: Configured proxy for development

### Authentication Flow
1. User redirected to Azure AD login
2. Azure AD validates credentials
3. Token returned to application
4. API calls made with Bearer token
5. Backend validates token against Azure AD

## 🚀 Deployment

### Environment Configuration

**Development:**
- Uses `localhost:3030` for redirects
- Proxy configuration for CORS
- Debug logging enabled

**Production:**
- Update redirect URIs in `.env` to production URLs
- Configure HTTPS certificates
- Disable debug logging
- Set proper CORS headers on backend

### Deployment Safety

**✅ Safe to Deploy:**
- All credentials in `.env` (not committed to Git)
- Azure AD handles authentication (no passwords stored)
- Tokens are short-lived and automatically refreshed
- Backend validates all API requests

**⚠️ Required for Production:**
- Update Azure App Registration with production URLs
- Configure HTTPS (required by Azure AD)
- Set up proper domain and SSL certificates
- Update environment variables for production

### Azure App Registration Setup

1. **Redirect URIs:** Add production URLs
2. **Logout URLs:** Configure post-logout redirects  
3. **API Permissions:** Ensure proper scopes granted
4. **Token Configuration:** Set token lifetime policies

## 🌐 Browser Support

- Modern browsers with ES2020+ support
- Chrome 80+, Firefox 80+, Safari 14+, Edge 80+

## 🛠️ Development

### Available Scripts
- `npm run dev` - Start development server
- `npm run build` - Build for production
- `npm run preview` - Preview production build
- `npm run lint` - Run ESLint

### Project Structure
```
src/
├── components/          # React components
├── hooks/              # Custom React hooks  
├── types/              # TypeScript definitions
├── config/             # Configuration files
├── styles/             # CSS files
└── utils/              # Utility functions
```

## 🔐 Environment Variables

Create `.env` file from `.env.example`:

| Variable | Description | Example |
|----------|-------------|---------|
| `VITE_MSAL_CLIENT_ID` | Azure App Client ID | `02992003-0b59-4610-...` |
| `VITE_MSAL_TENANT_ID` | Azure Tenant ID | `f251f123-c9ce-448e-...` |
| `VITE_MSAL_AUTHORITY` | Azure Authority URL | `https://login.microsoftonline.com/...` |
| `VITE_MSAL_REDIRECT_URI` | Redirect after login | `https://yourdomain.com` |
| `VITE_API_BASE_URL` | Backend API URL (set to `https://preview-api.security.ait.dtu.dk` for preview, etc.) | `https://api.security.ait.dtu.dk` |

## 📝 License

Developed for Danmarks Tekniske Universitet (DTU) - All rights reserved.
