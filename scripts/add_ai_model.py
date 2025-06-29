#!/usr/bin/env python3
"""
Script para agregar nuevos modelos de IA al sistema de monitoreo.

Uso:
    python scripts/add_ai_model.py
    python scripts/add_ai_model.py --provider gemini --model gemini-3.0-flash --input-price 0.0005 --output-price 0.002
"""

import sys
import os
import argparse
from datetime import datetime

# Agregar el directorio raíz al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.ai_monitoring.services import AIMonitoringService
from src.shared.database import get_db


def print_header():
    """Imprime el header del script."""
    print("=" * 60)
    print("🤖 SCRIPT DE GESTIÓN DE MODELOS DE IA")
    print("   Sistema de Monitoreo SapiensAI")
    print("=" * 60)


def print_supported_models():
    """Muestra los modelos actualmente soportados."""
    try:
        service = AIMonitoringService()
        models = service.get_supported_models()
        
        print("\n📋 MODELOS ACTUALMENTE SOPORTADOS:")
        print("-" * 40)
        
        for provider, provider_models in models.items():
            print(f"\n🔹 {provider.upper()}:")
            for model in provider_models:
                input_price = model['input_price_per_1k']
                output_price = model['output_price_per_1k']
                print(f"  • {model['model_name']}")
                print(f"    Input: ${input_price:.6f}/1K tokens")
                print(f"    Output: ${output_price:.6f}/1K tokens")
        
        print(f"\n✅ Total: {sum(len(models) for models in models.values())} modelos soportados")
        
    except Exception as e:
        print(f"❌ Error al obtener modelos: {str(e)}")


def add_model_interactive():
    """Modo interactivo para agregar un modelo."""
    print("\n🔧 MODO INTERACTIVO - AGREGAR NUEVO MODELO")
    print("-" * 45)
    
    # Solicitar datos del modelo
    print("\nProveedores disponibles: gemini, openai, claude")
    provider = input("Proveedor del modelo: ").strip().lower()
    
    if provider not in ['gemini', 'openai', 'claude']:
        print(f"❌ Proveedor '{provider}' no válido. Use: gemini, openai, claude")
        return False
    
    model_name = input("Nombre del modelo: ").strip()
    if not model_name:
        print("❌ El nombre del modelo no puede estar vacío")
        return False
    
    try:
        input_price = float(input("Precio por 1K tokens de entrada (USD): ").strip())
        output_price = float(input("Precio por 1K tokens de salida (USD): ").strip())
        
        if input_price < 0 or output_price < 0:
            print("❌ Los precios no pueden ser negativos")
            return False
            
    except ValueError:
        print("❌ Los precios deben ser números válidos")
        return False
    
    # Confirmación
    print(f"\n📝 RESUMEN DEL MODELO A AGREGAR:")
    print(f"   Proveedor: {provider}")
    print(f"   Modelo: {model_name}")
    print(f"   Precio entrada: ${input_price:.6f}/1K tokens")
    print(f"   Precio salida: ${output_price:.6f}/1K tokens")
    
    confirm = input("\n¿Confirmar agregar este modelo? (s/N): ").strip().lower()
    if confirm not in ['s', 'si', 'sí', 'y', 'yes']:
        print("❌ Operación cancelada")
        return False
    
    # Agregar el modelo
    return add_model(provider, model_name, input_price, output_price)


def add_model(provider, model_name, input_price, output_price):
    """Agrega un modelo al sistema."""
    try:
        print(f"\n⏳ Agregando modelo {provider}/{model_name}...")
        
        service = AIMonitoringService()
        success, message = service.add_custom_model_pricing(
            provider, model_name, input_price, output_price
        )
        
        if success:
            print(f"✅ {message}")
            print(f"   Modelo agregado exitosamente al sistema")
            return True
        else:
            print(f"❌ Error: {message}")
            return False
            
    except Exception as e:
        print(f"❌ Error inesperado: {str(e)}")
        return False


def check_model(provider, model_name):
    """Verifica si un modelo está soportado."""
    try:
        print(f"\n🔍 Verificando soporte para {provider}/{model_name}...")
        
        service = AIMonitoringService()
        prices = service._get_model_prices()
        
        is_supported = (
            provider in prices and 
            model_name in prices[provider]
        )
        
        if is_supported:
            model_pricing = prices[provider][model_name]
            print(f"✅ Modelo SOPORTADO")
            print(f"   Precio entrada: ${model_pricing['input']:.6f}/1K tokens")
            print(f"   Precio salida: ${model_pricing['output']:.6f}/1K tokens")
        else:
            print(f"❌ Modelo NO SOPORTADO")
            print(f"   Se usarán precios por defecto: $0.001 entrada, $0.002 salida")
        
        return is_supported
        
    except Exception as e:
        print(f"❌ Error al verificar modelo: {str(e)}")
        return False


def add_batch_models():
    """Agrega múltiples modelos de forma masiva."""
    print("\n📦 MODO LOTE - AGREGAR MÚLTIPLES MODELOS")
    print("-" * 45)
    
    # Modelos predefinidos que podrían faltar
    batch_models = [
        # Nuevos modelos Gemini 2.5 que el usuario mencionó
        ("gemini", "google/gemini-2.5-flash-preview", 0.0003, 0.0025),
        ("gemini", "gemini-2.5-flash-preview-04-17", 0.0003, 0.0025),
        ("gemini", "gemini-2.5-pro-preview-05-06", 0.00125, 0.01),
        
        # Otros modelos Gemini que podrían aparecer
        ("gemini", "gemini-2.5-flash-experimental", 0.0003, 0.0025),
        ("gemini", "gemini-2.5-pro-experimental", 0.00125, 0.01),
        
        # Modelos OpenAI recientes
        ("openai", "gpt-4o-2024-08-06", 0.0025, 0.01),
        ("openai", "gpt-4o-2024-11-20", 0.0025, 0.01),
        ("openai", "chatgpt-4o-latest", 0.005, 0.015),
        
        # Claude más recientes
        ("claude", "claude-3-5-sonnet-latest", 0.003, 0.015),
        ("claude", "claude-3-5-haiku-latest", 0.0008, 0.004),
    ]
    
    print(f"Se agregarán {len(batch_models)} modelos:")
    for provider, model, input_p, output_p in batch_models:
        print(f"  • {provider}/{model} (${input_p:.6f}/${output_p:.6f})")
    
    confirm = input(f"\n¿Continuar con la adición de {len(batch_models)} modelos? (s/N): ").strip().lower()
    if confirm not in ['s', 'si', 'sí', 'y', 'yes']:
        print("❌ Operación cancelada")
        return
    
    added_count = 0
    for provider, model_name, input_price, output_price in batch_models:
        if add_model(provider, model_name, input_price, output_price):
            added_count += 1
    
    print(f"\n✅ Proceso completado: {added_count}/{len(batch_models)} modelos agregados")


def main():
    parser = argparse.ArgumentParser(
        description="Gestiona modelos de IA en el sistema de monitoreo",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos de uso:
  python scripts/add_ai_model.py --list
  python scripts/add_ai_model.py --check --provider gemini --model gemini-2.5-flash
  python scripts/add_ai_model.py --provider gemini --model gemini-3.0-flash --input-price 0.0005 --output-price 0.002
  python scripts/add_ai_model.py --batch
        """
    )
    
    parser.add_argument('--provider', help='Proveedor del modelo (gemini, openai, claude)')
    parser.add_argument('--model', help='Nombre del modelo')
    parser.add_argument('--input-price', type=float, help='Precio por 1K tokens de entrada (USD)')
    parser.add_argument('--output-price', type=float, help='Precio por 1K tokens de salida (USD)')
    parser.add_argument('--list', action='store_true', help='Listar modelos soportados')
    parser.add_argument('--check', action='store_true', help='Verificar si un modelo está soportado')
    parser.add_argument('--batch', action='store_true', help='Agregar modelos en lote')
    
    args = parser.parse_args()
    
    print_header()
    
    try:
        # Verificar conexión a base de datos
        db = get_db()
        if db is None:
            print("❌ Error: No se pudo conectar a la base de datos")
            return 1
        
        # Ejecutar acción solicitada
        if args.list:
            print_supported_models()
            
        elif args.check:
            if not args.provider or not args.model:
                print("❌ Error: --check requiere --provider y --model")
                return 1
            check_model(args.provider, args.model)
            
        elif args.batch:
            add_batch_models()
            
        elif args.provider and args.model and args.input_price is not None and args.output_price is not None:
            # Modo línea de comandos
            if args.provider not in ['gemini', 'openai', 'claude']:
                print(f"❌ Proveedor '{args.provider}' no válido. Use: gemini, openai, claude")
                return 1
            
            add_model(args.provider, args.model, args.input_price, args.output_price)
            
        else:
            # Modo interactivo por defecto
            add_model_interactive()
        
        return 0
        
    except KeyboardInterrupt:
        print("\n\n❌ Operación cancelada por el usuario")
        return 1
    except Exception as e:
        print(f"\n❌ Error inesperado: {str(e)}")
        return 1


if __name__ == "__main__":
    exit(main()) 