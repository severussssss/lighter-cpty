#!/usr/bin/env python3
"""Compare performance between original and optimized orderbook streamers."""
import asyncio
import time
import psutil
import json
import redis
from datetime import datetime
from collections import defaultdict
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from typing import Dict, List, Tuple

# Test configuration
TEST_DURATION = 60  # seconds
SAMPLE_INTERVAL = 1  # seconds


class PerformanceMonitor:
    """Monitor performance metrics."""
    
    def __init__(self, process_name: str):
        self.process_name = process_name
        self.metrics = {
            'timestamps': [],
            'cpu_percent': [],
            'memory_mb': [],
            'redis_writes': [],
            'message_count': [],
            'orderbook_keys': []
        }
        self.redis_client = redis.Redis(host='localhost', port=6379, db=2, decode_responses=True)
        self.last_redis_info = None
        self.start_time = time.time()
        
    def find_process(self):
        """Find process by name."""
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = ' '.join(proc.info['cmdline'] or [])
                if self.process_name in cmdline:
                    return proc
            except:
                continue
        return None
        
    def collect_metrics(self):
        """Collect current metrics."""
        timestamp = time.time() - self.start_time
        self.metrics['timestamps'].append(timestamp)
        
        # Process metrics
        proc = self.find_process()
        if proc:
            try:
                self.metrics['cpu_percent'].append(proc.cpu_percent(interval=0.1))
                self.metrics['memory_mb'].append(proc.memory_info().rss / 1024 / 1024)
            except:
                self.metrics['cpu_percent'].append(0)
                self.metrics['memory_mb'].append(0)
        else:
            self.metrics['cpu_percent'].append(0)
            self.metrics['memory_mb'].append(0)
            
        # Redis metrics
        try:
            redis_info = self.redis_client.info('commandstats')
            
            # Calculate Redis writes per second
            setex_calls = redis_info.get('cmdstat_setex', {}).get('calls', 0)
            if self.last_redis_info:
                last_setex = self.last_redis_info.get('cmdstat_setex', {}).get('calls', 0)
                writes_per_sec = setex_calls - last_setex
            else:
                writes_per_sec = 0
                
            self.metrics['redis_writes'].append(writes_per_sec)
            self.last_redis_info = redis_info
            
            # Count orderbook keys
            orderbook_count = len(self.redis_client.keys('l2_book:*'))
            self.metrics['orderbook_keys'].append(orderbook_count)
            
        except:
            self.metrics['redis_writes'].append(0)
            self.metrics['orderbook_keys'].append(0)


async def test_streamer(script_name: str, test_name: str, markets: int) -> Dict:
    """Test a specific streamer implementation."""
    print(f"\n{'='*60}")
    print(f"Testing: {test_name}")
    print(f"Markets: {markets}")
    print(f"Script: {script_name}")
    print(f"{'='*60}")
    
    # Start the streamer
    process = await asyncio.create_subprocess_exec(
        'python', script_name,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL
    )
    
    # Wait for startup
    await asyncio.sleep(5)
    
    # Monitor performance
    monitor = PerformanceMonitor(script_name)
    
    print(f"Collecting metrics for {TEST_DURATION} seconds...")
    for i in range(TEST_DURATION):
        monitor.collect_metrics()
        await asyncio.sleep(SAMPLE_INTERVAL)
        
        # Progress indicator
        if i % 10 == 0:
            print(f"  {i}/{TEST_DURATION} seconds...")
    
    # Stop the process
    process.terminate()
    await process.wait()
    
    # Calculate averages (exclude first 10 seconds for warmup)
    warmup_samples = 10
    metrics_stable = {
        'avg_cpu': sum(monitor.metrics['cpu_percent'][warmup_samples:]) / max(1, len(monitor.metrics['cpu_percent'][warmup_samples:])),
        'avg_memory': sum(monitor.metrics['memory_mb'][warmup_samples:]) / max(1, len(monitor.metrics['memory_mb'][warmup_samples:])),
        'avg_redis_writes': sum(monitor.metrics['redis_writes'][warmup_samples:]) / max(1, len(monitor.metrics['redis_writes'][warmup_samples:])),
        'max_orderbooks': max(monitor.metrics['orderbook_keys'][warmup_samples:] or [0]),
    }
    
    print(f"\nResults for {test_name}:")
    print(f"  Average CPU: {metrics_stable['avg_cpu']:.1f}%")
    print(f"  Average Memory: {metrics_stable['avg_memory']:.1f} MB")
    print(f"  Average Redis Writes/s: {metrics_stable['avg_redis_writes']:.1f}")
    print(f"  Max Orderbook Keys: {metrics_stable['max_orderbooks']}")
    
    return {
        'name': test_name,
        'markets': markets,
        'metrics': monitor.metrics,
        'averages': metrics_stable
    }


def create_visualizations(results: List[Dict]):
    """Create performance comparison visualizations."""
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 10))
    fig.suptitle('Orderbook Streamer Performance Comparison', fontsize=16)
    
    colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4']
    
    # 1. CPU Usage Over Time
    ax1.set_title('CPU Usage Over Time')
    ax1.set_xlabel('Time (seconds)')
    ax1.set_ylabel('CPU Usage (%)')
    ax1.grid(True, alpha=0.3)
    
    for i, result in enumerate(results):
        ax1.plot(result['metrics']['timestamps'], 
                result['metrics']['cpu_percent'], 
                label=result['name'], 
                color=colors[i],
                linewidth=2)
    ax1.legend()
    
    # 2. Memory Usage Over Time
    ax2.set_title('Memory Usage Over Time')
    ax2.set_xlabel('Time (seconds)')
    ax2.set_ylabel('Memory (MB)')
    ax2.grid(True, alpha=0.3)
    
    for i, result in enumerate(results):
        ax2.plot(result['metrics']['timestamps'], 
                result['metrics']['memory_mb'], 
                label=result['name'], 
                color=colors[i],
                linewidth=2)
    ax2.legend()
    
    # 3. Redis Writes Comparison
    ax3.set_title('Redis Write Operations')
    test_names = [r['name'] for r in results]
    avg_writes = [r['averages']['avg_redis_writes'] for r in results]
    markets = [r['markets'] for r in results]
    
    x_pos = range(len(test_names))
    bars = ax3.bar(x_pos, avg_writes, color=colors[:len(results)])
    ax3.set_xticks(x_pos)
    ax3.set_xticklabels(test_names, rotation=45, ha='right')
    ax3.set_ylabel('Average Writes/Second')
    ax3.grid(True, axis='y', alpha=0.3)
    
    # Add value labels on bars
    for i, (bar, writes, mkts) in enumerate(zip(bars, avg_writes, markets)):
        height = bar.get_height()
        ax3.text(bar.get_x() + bar.get_width()/2., height,
                f'{writes:.0f}\n({mkts} mkts)',
                ha='center', va='bottom')
    
    # 4. Efficiency Metrics
    ax4.set_title('Performance Efficiency')
    
    # Calculate efficiency scores
    categories = ['CPU\nEfficiency', 'Memory\nEfficiency', 'Redis\nEfficiency', 'Overall\nScore']
    
    # Normalize metrics (lower is better for all)
    efficiency_data = []
    for result in results:
        avg = result['averages']
        markets = result['markets']
        
        # Normalize per market
        cpu_eff = 100 - min(100, (avg['avg_cpu'] / markets) * 10)  # Lower CPU per market is better
        mem_eff = 100 - min(100, (avg['avg_memory'] / markets) * 0.5)  # Lower memory per market is better
        redis_eff = 100 - min(100, (avg['avg_redis_writes'] / markets) * 0.5)  # Fewer writes per market is better
        overall = (cpu_eff + mem_eff + redis_eff) / 3
        
        efficiency_data.append([cpu_eff, mem_eff, redis_eff, overall])
    
    x = range(len(categories))
    width = 0.35
    
    for i, (result, eff_data) in enumerate(zip(results, efficiency_data)):
        offset = (i - len(results)/2 + 0.5) * width
        ax4.bar([xi + offset for xi in x], eff_data, 
               width, label=result['name'], color=colors[i])
    
    ax4.set_ylabel('Efficiency Score (0-100)')
    ax4.set_xticks(x)
    ax4.set_xticklabels(categories)
    ax4.legend()
    ax4.grid(True, axis='y', alpha=0.3)
    ax4.set_ylim(0, 110)
    
    plt.tight_layout()
    plt.savefig('orderbook_performance_comparison.png', dpi=300, bbox_inches='tight')
    print(f"\nVisualization saved to orderbook_performance_comparison.png")


async def main():
    """Run performance comparison tests."""
    print("Orderbook Streamer Performance Comparison")
    print("=========================================")
    
    # Clear Redis before starting
    r = redis.Redis(host='localhost', port=6379, db=2)
    r.flushdb()
    print("Cleared Redis database")
    
    results = []
    
    # Test 1: Original streamer with 17 markets
    # First, create a version of original streamer with 17 markets
    with open('run_orderbook_streamer.py', 'r') as f:
        original_code = f.read()
    
    # Limit to 17 markets
    limited_code = original_code.replace(
        '    markets_to_stream = [',
        '    markets_to_stream = [\n        # Limited to 17 markets for testing'
    ).replace(
        '        15,  # TRUMP\n    ]',
        '        15,  # TRUMP\n    ][:17]  # Limit to 17 markets'
    )
    
    with open('test_original_17.py', 'w') as f:
        f.write(limited_code)
    
    result1 = await test_streamer('test_original_17.py', 'Original (17 markets)', 17)
    results.append(result1)
    
    # Test 2: Optimized streamer with 17 markets (fair comparison)
    with open('run_orderbook_streamer_optimized.py', 'r') as f:
        optimized_code = f.read()
    
    # Limit to 17 markets for fair comparison
    limited_opt_code = optimized_code.replace(
        '    markets_to_stream = list(range(45))',
        '    markets_to_stream = list(range(17))'
    )
    
    with open('test_optimized_17.py', 'w') as f:
        f.write(limited_opt_code)
        
    result2 = await test_streamer('test_optimized_17.py', 'Optimized (17 markets)', 17)
    results.append(result2)
    
    # Test 3: Optimized streamer with all 45 markets
    result3 = await test_streamer('run_orderbook_streamer_optimized.py', 'Optimized (45 markets)', 45)
    results.append(result3)
    
    # Create visualizations
    create_visualizations(results)
    
    # Print summary
    print("\n" + "="*60)
    print("PERFORMANCE SUMMARY")
    print("="*60)
    
    print("\nResource Usage Comparison:")
    print(f"{'Streamer':<25} {'Markets':<10} {'CPU %':<10} {'Memory MB':<12} {'Redis/s':<10}")
    print("-"*70)
    
    for result in results:
        avg = result['averages']
        print(f"{result['name']:<25} {result['markets']:<10} "
              f"{avg['avg_cpu']:<10.1f} {avg['avg_memory']:<12.1f} "
              f"{avg['avg_redis_writes']:<10.1f}")
    
    # Calculate improvements
    if len(results) >= 2:
        orig_17 = results[0]['averages']
        opt_17 = results[1]['averages']
        
        cpu_improvement = (orig_17['avg_cpu'] - opt_17['avg_cpu']) / orig_17['avg_cpu'] * 100
        mem_improvement = (orig_17['avg_memory'] - opt_17['avg_memory']) / orig_17['avg_memory'] * 100
        redis_improvement = (orig_17['avg_redis_writes'] - opt_17['avg_redis_writes']) / orig_17['avg_redis_writes'] * 100
        
        print(f"\nImprovements (Optimized vs Original, 17 markets):")
        print(f"  CPU Usage: {cpu_improvement:.1f}% reduction")
        print(f"  Memory Usage: {mem_improvement:.1f}% reduction")
        print(f"  Redis Writes: {redis_improvement:.1f}% reduction")
        
    if len(results) >= 3:
        opt_17 = results[1]['averages']
        opt_45 = results[2]['averages']
        
        # Per-market efficiency
        cpu_per_market_17 = opt_17['avg_cpu'] / 17
        cpu_per_market_45 = opt_45['avg_cpu'] / 45
        
        print(f"\nScalability Analysis:")
        print(f"  CPU per market (17 markets): {cpu_per_market_17:.2f}%")
        print(f"  CPU per market (45 markets): {cpu_per_market_45:.2f}%")
        print(f"  Scaling efficiency: {(1 - cpu_per_market_45/cpu_per_market_17) * 100:.1f}% better at scale")
    
    # Cleanup
    import os
    os.remove('test_original_17.py')
    os.remove('test_optimized_17.py')


if __name__ == "__main__":
    # Install matplotlib if needed
    try:
        import matplotlib
    except ImportError:
        import subprocess
        print("Installing matplotlib...")
        subprocess.check_call(['pip', 'install', 'matplotlib'])
        
    asyncio.run(main())