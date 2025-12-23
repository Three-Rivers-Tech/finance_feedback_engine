#!/bin/bash
# DVC Setup Script for Finance Feedback Engine
# This script initializes DVC and sets up data versioning

set -e  # Exit on error

echo "========================================="
echo "DVC Setup for Finance Feedback Engine"
echo "========================================="
echo ""

# Check if DVC is installed
if ! command -v dvc &> /dev/null; then
    echo "❌ DVC not found. Installing..."
    pip install dvc
else
    echo "✓ DVC is installed: $(dvc version)"
fi

# Check if DVC is already initialized
if [ -d ".dvc" ]; then
    echo "✓ DVC already initialized"
else
    echo "Initializing DVC..."
    dvc init
    echo "✓ DVC initialized"
fi

# Prompt for remote storage type
echo ""
echo "Configure DVC remote storage:"
echo "1) Local directory (testing/development)"
echo "2) AWS S3"
echo "3) Google Cloud Storage"
echo "4) Skip (configure later)"
echo ""
read -p "Choose option [1-4]: " storage_option

case $storage_option in
    1)
        read -p "Enter local storage path (e.g., /tmp/dvc-storage): " local_path
        dvc remote add -d local_storage "$local_path"
        echo "✓ Local storage configured: $local_path"
        ;;
    2)
        read -p "Enter S3 bucket URL (e.g., s3://my-bucket/dvc-storage): " s3_url
        dvc remote add -d s3_storage "$s3_url"
        echo "✓ S3 storage configured: $s3_url"
        echo "Remember to set AWS credentials:"
        echo "  export AWS_ACCESS_KEY_ID=<your-key>"
        echo "  export AWS_SECRET_ACCESS_KEY=<your-secret>"
        ;;
    3)
        read -p "Enter GCS bucket URL (e.g., gs://my-bucket/dvc-storage): " gcs_url
        dvc remote add -d gcs_storage "$gcs_url"
        echo "✓ GCS storage configured: $gcs_url"
        echo "Remember to authenticate: gcloud auth application-default login"
        ;;
    4)
        echo "Skipped remote configuration. Configure later with:"
        echo "  dvc remote add -d <name> <url>"
        ;;
    *)
        echo "Invalid option. Skipping remote configuration."
        ;;
esac

# Add data directories to DVC
echo ""
echo "Adding data directories to DVC tracking..."

# Create directories if they don't exist
mkdir -p data/decisions
mkdir -p data/optimization
mkdir -p data/backtest_results

# Track with DVC
if [ -f "data/backtest_cache.db" ]; then
    dvc add data/backtest_cache.db
    echo "✓ Added: data/backtest_cache.db"
fi

if [ -d "data/decisions" ] && [ "$(ls -A data/decisions)" ]; then
    dvc add data/decisions/
    echo "✓ Added: data/decisions/"
fi

if [ -d "data/optimization" ] && [ "$(ls -A data/optimization)" ]; then
    dvc add data/optimization/
    echo "✓ Added: data/optimization/"
fi

# Add .dvc files to git
echo ""
echo "Adding DVC files to git..."
git add .dvc/.gitignore .dvc/config
if [ -f "data/backtest_cache.db.dvc" ]; then
    git add data/backtest_cache.db.dvc
fi
if [ -f "data/decisions.dvc" ]; then
    git add data/decisions.dvc
fi
if [ -f "data/optimization.dvc" ]; then
    git add data/optimization.dvc
fi
git add data/.gitignore

echo "✓ DVC files staged for commit"

echo ""
echo "========================================="
echo "DVC Setup Complete!"
echo "========================================="
echo ""
echo "Next steps:"
echo "  1. Commit DVC files: git commit -m 'Initialize DVC'"
echo "  2. Run experiment: python experiments/run_full_experiment.py"
echo "  3. Push data: dvc push"
echo ""
echo "Useful commands:"
echo "  dvc status     - Check data status"
echo "  dvc push       - Upload data to remote"
echo "  dvc pull       - Download data from remote"
echo "  dvc diff       - Show data changes"
echo ""
