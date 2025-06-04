#!/bin/bash
set -e

# Instalar dependências do backend
pip install -r backend/requirements.txt

# Instalar dependências do frontend
cd frontend
npm install
