import React, { useCallback, useMemo } from 'react';
import './SwaggerDocsModal.css';

interface SwaggerDocsModalProps {
  accessToken: string | null;
  onClose: () => void;
}

const SWAGGER_SPEC_URL = 'https://api.security.ait.dtu.dk/myview/swagger/?format=openapi';

const SwaggerDocsModal: React.FC<SwaggerDocsModalProps> = ({ accessToken, onClose }) => {
  const swaggerHtmlDocument = useMemo(() => {
    const encodedSpecUrl = JSON.stringify(SWAGGER_SPEC_URL);
    const encodedToken = accessToken ? JSON.stringify(accessToken) : 'null';

    return `<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Swagger UI</title>
    <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css" />
    <style>
      body { margin: 0; background: #f5f5f5; }
      #swagger-ui { height: 100vh; }
    </style>
  </head>
  <body>
    <div id="swagger-ui"></div>
    <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
    <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-standalone-preset.js"></script>
    <script>
      (function () {
        const swaggerSpecUrl = ${encodedSpecUrl};
        const accessToken = ${encodedToken};

        window.ui = SwaggerUIBundle({
          url: swaggerSpecUrl,
          dom_id: '#swagger-ui',
          presets: [SwaggerUIBundle.presets.apis, SwaggerUIStandalonePreset],
          layout: 'BaseLayout',
          deepLinking: true,
          requestInterceptor: (req) => {
            if (accessToken) {
              req.headers = req.headers || {};
              req.headers.Authorization = 'Bearer ' + accessToken;
            }
            return req;
          },
        });
      })();
    </script>
  </body>
</html>`;
  }, [accessToken]);

  const handleOverlayClick = (event: React.MouseEvent<HTMLDivElement>) => {
    if (event.target === event.currentTarget) {
      onClose();
    }
  };

  const handleOpenInNewTab = useCallback(() => {
    if (!swaggerHtmlDocument) {
      window.open('https://api.security.ait.dtu.dk/myview/swagger/', '_blank', 'noopener,noreferrer');
      return;
    }

    const blob = new Blob([swaggerHtmlDocument], { type: 'text/html' });
    const blobUrl = URL.createObjectURL(blob);
    window.open(blobUrl, '_blank', 'noopener,noreferrer');

    window.setTimeout(() => URL.revokeObjectURL(blobUrl), 60_000);
  }, [swaggerHtmlDocument]);

  return (
    <div className="swagger-modal-overlay" onClick={handleOverlayClick}>
      <div className="swagger-modal-content">
        <header className="swagger-modal-header">
          <div>
            <h2>📘 Backend Swagger UI</h2>
            <p>
              Explore and test the backend API endpoints directly from the embedded Swagger UI.
            </p>
          </div>
          <div className="swagger-modal-actions">
            <button className="swagger-open-link" onClick={handleOpenInNewTab} type="button">
              Open in new tab
            </button>
            <button className="swagger-close-button" onClick={onClose} aria-label="Close swagger modal">
              ×
            </button>
          </div>
        </header>
        <div className="swagger-iframe-container">
          <iframe
            srcDoc={swaggerHtmlDocument}
            title="Backend Swagger Documentation"
            className="swagger-iframe"
            sandbox="allow-same-origin allow-scripts allow-forms allow-popups"
          />
        </div>
      </div>
    </div>
  );
};

export default SwaggerDocsModal;
