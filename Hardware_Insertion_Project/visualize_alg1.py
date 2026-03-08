"""
Visualization Script for Algorithm 1 Validation Results
Generates plots to compare with Paper Figure 2 and Figure 3
"""

import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path

# Set style for better-looking plots
plt.style.use('seaborn-v0_8-darkgrid')

def plot_figure2():
    """
    Figure 2: Rare Node Percentage vs. Threshold
    Shows how the percentage of rare nodes changes with different thresholds
    """
    df = pd.read_csv('validation_fig2.csv')
    
    # Get unique circuits
    circuits = df['Circuit'].unique()
    
    # Create figure with proper size
    fig, ax = plt.subplots(figsize=(12, 8))
    
    # Plot each circuit
    for circuit in circuits:
        circuit_data = df[df['Circuit'] == circuit]
        ax.plot(circuit_data['Threshold'], 
                circuit_data['RarePercentage'],
                marker='o', 
                linewidth=2,
                markersize=8,
                label=circuit)
    
    ax.set_xlabel('Threshold (% of test vectors)', fontsize=14, fontweight='bold')
    ax.set_ylabel('Percentage of Rare Nodes (%)', fontsize=14, fontweight='bold')
    ax.set_title('Figure 2: Rare Node Distribution vs. Threshold\n(10,000 test vectors)', 
                 fontsize=16, fontweight='bold', pad=20)
    ax.legend(loc='upper left', fontsize=12, ncol=2)
    ax.grid(True, alpha=0.3)
    ax.set_xlim(4, 31)
    ax.set_ylim(0, max(df['RarePercentage']) + 5)
    
    plt.tight_layout()
    plt.savefig('validation_fig2_plot.png', dpi=300, bbox_inches='tight')
    print("[OK] Figure 2 plot saved: validation_fig2_plot.png")
    plt.close()

def plot_figure3():
    """
    Figure 3: Rare Node Count vs. Number of Test Vectors
    Shows how the number of rare nodes changes with more test vectors
    """
    df = pd.read_csv('validation_fig3.csv')
    
    # Get unique circuits
    circuits = df['Circuit'].unique()
    
    # Create figure with proper size
    fig, ax = plt.subplots(figsize=(12, 8))
    
    # Plot each circuit
    for circuit in circuits:
        circuit_data = df[df['Circuit'] == circuit]
        ax.plot(circuit_data['NumVectors'], 
                circuit_data['RareNodes'],
                marker='s', 
                linewidth=2,
                markersize=8,
                label=circuit)
    
    ax.set_xlabel('Number of Test Vectors', fontsize=14, fontweight='bold')
    ax.set_ylabel('Number of Rare Nodes', fontsize=14, fontweight='bold')
    ax.set_title('Figure 3: Rare Node Count vs. Test Vector Count\n(Threshold = 20%)', 
                 fontsize=16, fontweight='bold', pad=20)
    ax.legend(loc='upper right', fontsize=12, ncol=2)
    ax.grid(True, alpha=0.3)
    ax.set_xlim(0, 21000)
    
    plt.tight_layout()
    plt.savefig('validation_fig3_plot.png', dpi=300, bbox_inches='tight')
    print("[OK] Figure 3 plot saved: validation_fig3_plot.png")
    plt.close()

def generate_statistics_table():
    """
    Generate a summary statistics table for the validation results
    """
    df2 = pd.read_csv('validation_fig2.csv')
    df3 = pd.read_csv('validation_fig3.csv')
    
    print("\n" + "="*80)
    print("ALGORITHM 1 VALIDATION SUMMARY")
    print("="*80)
    
    print("\n[TABLE 1] Circuit Statistics")
    print("-" * 80)
    print(f"{'Circuit':<12} {'Total Nodes':<15} {'Rare @ 20%':<15} {'Rare %':<15}")
    print("-" * 80)
    
    for circuit in df2['Circuit'].unique():
        circuit_data_fig2 = df2[(df2['Circuit'] == circuit) & (df2['Threshold'] == 20.0)]
        if not circuit_data_fig2.empty:
            total_nodes = circuit_data_fig2['TotalNodes'].values[0]
            rare_nodes = circuit_data_fig2['RareNodes'].values[0]
            rare_pct = circuit_data_fig2['RarePercentage'].values[0]
            print(f"{circuit:<12} {total_nodes:<15} {rare_nodes:<15} {rare_pct:<15.2f}")
    
    print("\n[TABLE 2] Rare Node Stability (Figure 3 Analysis)")
    print("-" * 80)
    print(f"{'Circuit':<12} {'Min Rare':<12} {'Max Rare':<12} {'Variation':<15} {'Stable?':<10}")
    print("-" * 80)
    
    for circuit in df3['Circuit'].unique():
        circuit_data = df3[df3['Circuit'] == circuit]
        min_rare = circuit_data['RareNodes'].min()
        max_rare = circuit_data['RareNodes'].max()
        variation = max_rare - min_rare
        stable = "Yes" if variation < (max_rare * 0.1) else "No"
        print(f"{circuit:<12} {min_rare:<12} {max_rare:<12} {variation:<15} {stable:<10}")
    
    print("\n[TABLE 3] Anomaly Detection")
    print("-" * 80)
    print(f"{'Circuit':<12} {'Issue Detected':<50}")
    print("-" * 80)
    
    # Check s35932 anomaly
    s35932_fig2 = df2[df2['Circuit'] == 's35932']
    if len(s35932_fig2) > 0:
        zero_rare = s35932_fig2[s35932_fig2['RareNodes'] == 0]
        if len(zero_rare) > 0:
            print(f"{'s35932':<12} {'0% rare nodes for thresholds 5%-20%, jumps at 25%':<50}")
    
    s35932_fig3 = df3[df3['Circuit'] == 's35932']
    if len(s35932_fig3) > 0:
        if s35932_fig3['RareNodes'].max() <= 1:
            print(f"{'s35932':<12} {'Nearly 0% rare nodes across all vector counts':<50}")
    
    print("="*80)

def main():
    print(">> Generating Algorithm 1 Validation Visualizations...")
    print("-" * 80)
    
    # Check if CSV files exist
    if not Path('validation_fig2.csv').exists():
        print("ERROR: validation_fig2.csv not found!")
        return
    
    if not Path('validation_fig3.csv').exists():
        print("ERROR: validation_fig3.csv not found!")
        return
    
    # Generate plots
    plot_figure2()
    plot_figure3()
    
    # Generate statistics
    generate_statistics_table()
    
    print("\n[SUCCESS] Visualization complete!")
    print("\nGenerated files:")
    print("  1. validation_fig2_plot.png - Rare nodes vs. Threshold")
    print("  2. validation_fig3_plot.png - Rare nodes vs. Test vectors")
    print("\nNext step: Review plots and compare with paper Figures 2 & 3")

if __name__ == "__main__":
    main()
