#!/bin/bash
# Deploy Praval documentation to praval-ai website
# Usage: ./scripts/deploy-docs.sh [version]

set -e

# Get the project root directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

# Get version from __init__.py if not provided
if [ -z "$1" ]; then
    VERSION=$(grep "__version__" "$PROJECT_ROOT/src/praval/__init__.py" | cut -d'"' -f2)
else
    VERSION=$1
fi

# Configuration
DOCS_BUILD_DIR="$PROJECT_ROOT/docs/_build/html"
WEBSITE_REPO="$HOME/Github/praval-ai"
WEBSITE_DOCS_DIR="$WEBSITE_REPO/docs"

echo "📚 Deploying Praval Documentation v$VERSION"
echo "================================================"

# Check if docs are built
if [ ! -d "$DOCS_BUILD_DIR" ]; then
    echo "❌ Documentation not built. Run 'make docs-html' first."
    exit 1
fi

# Check if website repo exists
if [ ! -d "$WEBSITE_REPO" ]; then
    echo "❌ Website repository not found at: $WEBSITE_REPO"
    exit 1
fi

# Create docs directories
echo "📁 Creating documentation directories..."
mkdir -p "$WEBSITE_DOCS_DIR/v$VERSION"
mkdir -p "$WEBSITE_DOCS_DIR/latest"

# Copy documentation to versioned directory
echo "📋 Copying documentation to v$VERSION..."
rsync -av --delete "$DOCS_BUILD_DIR/" "$WEBSITE_DOCS_DIR/v$VERSION/"

# Copy to latest directory
echo "📋 Updating latest documentation..."
rsync -av --delete "$DOCS_BUILD_DIR/" "$WEBSITE_DOCS_DIR/latest/"

# Update versions.json for version switcher (preserving historical versions)
echo "📝 Updating versions.json..."
if [ -f "$WEBSITE_DOCS_DIR/versions.json" ]; then
    # Read existing versions (excluding current and latest entries)
    EXISTING_VERSIONS=$(python3 -c "
import json
with open('$WEBSITE_DOCS_DIR/versions.json') as f:
    data = json.load(f)
existing = [v for v in data.get('versions', []) if v['version'] not in ['latest', '$VERSION']]
# Output as JSON array
print(json.dumps(existing))
" 2>/dev/null || echo "[]")
else
    EXISTING_VERSIONS="[]"
fi

# Create new versions.json with current version at top and preserved history
python3 -c "
import json

existing = $EXISTING_VERSIONS

# Build new versions list
versions = [
    {'version': '$VERSION', 'url': '/docs/v$VERSION/', 'title': 'v$VERSION (latest)'},
    {'version': 'latest', 'url': '/docs/latest/', 'title': 'Latest (v$VERSION)'}
]

# Add existing versions (they're already filtered)
versions.extend(existing)

# Create the full structure
data = {
    'current': '$VERSION',
    'latest': '$VERSION',
    'versions': versions
}

with open('$WEBSITE_DOCS_DIR/versions.json', 'w') as f:
    json.dump(data, f, indent=2)
"
echo "   ✓ versions.json updated with historical versions preserved"

# Create docs index page
echo "📝 Creating docs index page..."
cat > "$WEBSITE_DOCS_DIR/index.html" <<'EOF'
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Praval Documentation</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background: linear-gradient(135deg, #1e1e1e 0%, #2d2d2d 100%);
            color: #e0e0e0;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 2rem;
        }
        .container {
            max-width: 800px;
            background: #161616;
            border-radius: 12px;
            padding: 3rem;
            box-shadow: 0 10px 30px rgba(0,0,0,0.3);
        }
        h1 {
            color: #FF6B35;
            font-size: 2.5rem;
            margin-bottom: 1rem;
            border-bottom: 3px solid #FF6B35;
            padding-bottom: 1rem;
        }
        p {
            color: #b0b0b0;
            font-size: 1.1rem;
            margin-bottom: 2rem;
            line-height: 1.6;
        }
        .versions {
            display: grid;
            gap: 1rem;
        }
        .version-card {
            background: #2d2d2d;
            border: 2px solid #FF6B35;
            border-radius: 8px;
            padding: 1.5rem;
            text-decoration: none;
            color: #e0e0e0;
            transition: all 0.3s ease;
        }
        .version-card:hover {
            background: #FF6B35;
            color: #161616;
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(255, 107, 53, 0.3);
        }
        .version-title {
            font-size: 1.5rem;
            font-weight: bold;
            margin-bottom: 0.5rem;
        }
        .version-desc {
            color: #b0b0b0;
        }
        .version-card:hover .version-desc {
            color: #161616;
        }
        .badge {
            display: inline-block;
            background: #FF6B35;
            color: #161616;
            padding: 0.25rem 0.75rem;
            border-radius: 4px;
            font-size: 0.85rem;
            font-weight: bold;
            margin-left: 0.5rem;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>📚 Praval Documentation</h1>
        <p>Choose a documentation version to view:</p>
        <div class="versions" id="versions-list">
            <a href="latest/" class="version-card">
                <div class="version-title">
                    Latest Documentation
                    <span class="badge">RECOMMENDED</span>
                </div>
                <div class="version-desc">Always up-to-date with the latest release</div>
            </a>
        </div>
    </div>

    <script>
        // Load versions from versions.json and populate the list
        fetch('versions.json')
            .then(response => response.json())
            .then(data => {
                const container = document.getElementById('versions-list');
                data.versions.forEach((version, index) => {
                    if (version.version !== 'latest') {
                        const card = document.createElement('a');
                        card.href = version.url;
                        card.className = 'version-card';
                        card.innerHTML = `
                            <div class="version-title">${version.title}</div>
                            <div class="version-desc">Documentation for Praval ${version.version}</div>
                        `;
                        container.appendChild(card);
                    }
                });
            });
    </script>
</body>
</html>
EOF

echo ""
echo "✅ Documentation deployed successfully!"
echo ""
echo "📍 Locations:"
echo "   Versioned: $WEBSITE_DOCS_DIR/v$VERSION/"
echo "   Latest:    $WEBSITE_DOCS_DIR/latest/"
echo "   Index:     $WEBSITE_DOCS_DIR/index.html"
echo ""
echo "🌐 URLs (when deployed):"
echo "   https://yourdomain.com/docs/v$VERSION/"
echo "   https://yourdomain.com/docs/latest/"
echo "   https://yourdomain.com/docs/"
echo ""
echo "📋 Next steps:"
echo "   1. cd $WEBSITE_REPO"
echo "   2. git add docs/"
echo "   3. git commit -m 'docs: Add Praval v$VERSION documentation'"
echo "   4. git push"
