#!/usr/bin/env python3
"""
Wiki Knowledge Graph Generator
Parses all markdown files and generates an interactive graph visualization.
"""

import os
import re
import json
import yaml
from pathlib import Path
from collections import defaultdict


def parse_frontmatter(content):
    """Extract YAML frontmatter from markdown content."""
    if content.startswith('---'):
        parts = content.split('---', 2)
        if len(parts) >= 3:
            try:
                return yaml.safe_load(parts[1]) or {}
            except:
                return {}
    return {}


def extract_wikilinks(content):
    """Extract all [[wikilink]] references from content."""
    # Match [[page]] or [[page|display text]]
    pattern = r'\[\[([^\]|]+)(?:\|[^\]]*)?\]\]'
    return re.findall(pattern, content)


def build_graph(wiki_dir):
    """Build the knowledge graph from all markdown files."""
    nodes = {}
    edges = []
    tag_groups = defaultdict(list)
    
    # Find all markdown files
    md_files = list(Path(wiki_dir).rglob('*.md'))
    
    for md_file in md_files:
        # Skip archive and hidden files
        if '_archive' in str(md_file) or md_file.name.startswith('_'):
            continue
            
        rel_path = md_file.relative_to(wiki_dir)
        content = md_file.read_text(encoding='utf-8')
        
        # Parse frontmatter
        frontmatter = parse_frontmatter(content)
        
        # Extract page info
        page_id = str(rel_path.with_suffix(''))
        title = frontmatter.get('title', md_file.stem.replace('-', ' ').title())
        page_type = frontmatter.get('type', 'note')
        tags = frontmatter.get('tags', [])
        
        # Add node
        nodes[page_id] = {
            'id': page_id,
            'title': title,
            'type': page_type,
            'tags': tags,
            'path': str(rel_path)
        }
        
        # Group by tags
        for tag in tags:
            tag_groups[tag].append(page_id)
        
        # Extract wikilinks
        links = extract_wikilinks(content)
        for link in links:
            # Normalize link (remove .md extension if present)
            target = link.replace('.md', '')
            edges.append({
                'source': page_id,
                'target': target,
                'type': 'links_to'
            })
    
    return {
        'nodes': list(nodes.values()),
        'edges': edges,
        'tag_groups': dict(tag_groups),
        'stats': {
            'total_pages': len(nodes),
            'total_links': len(edges),
            'total_tags': len(tag_groups)
        }
    }


def generate_graph_html(graph_data, output_path):
    """Generate interactive HTML page with D3.js graph."""
    
    html_template = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Wiki Knowledge Graph</title>
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: #0d1117;
            color: #c9d1d9;
            overflow: hidden;
        }
        .header {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            padding: 15px 20px;
            background: rgba(13, 17, 23, 0.9);
            backdrop-filter: blur(10px);
            border-bottom: 1px solid #30363d;
            z-index: 100;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .header h1 {
            font-size: 18px;
            font-weight: 600;
            color: #58a6ff;
        }
        .stats {
            display: flex;
            gap: 20px;
            font-size: 13px;
            color: #8b949e;
        }
        .stat-item {
            display: flex;
            align-items: center;
            gap: 5px;
        }
        .stat-value {
            color: #58a6ff;
            font-weight: 600;
        }
        #graph-container {
            width: 100vw;
            height: 100vh;
            cursor: grab;
        }
        #graph-container:active {
            cursor: grabbing;
        }
        .controls {
            position: fixed;
            bottom: 20px;
            left: 20px;
            display: flex;
            flex-direction: column;
            gap: 10px;
            z-index: 100;
        }
        .control-btn {
            width: 40px;
            height: 40px;
            border-radius: 8px;
            border: 1px solid #30363d;
            background: rgba(22, 27, 34, 0.9);
            color: #c9d1d9;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 18px;
            transition: all 0.2s;
        }
        .control-btn:hover {
            background: #30363d;
            border-color: #58a6ff;
        }
        .legend {
            position: fixed;
            bottom: 20px;
            right: 20px;
            background: rgba(22, 27, 34, 0.9);
            border: 1px solid #30363d;
            border-radius: 8px;
            padding: 15px;
            z-index: 100;
            font-size: 12px;
        }
        .legend-title {
            font-weight: 600;
            margin-bottom: 10px;
            color: #58a6ff;
        }
        .legend-item {
            display: flex;
            align-items: center;
            gap: 8px;
            margin: 5px 0;
        }
        .legend-dot {
            width: 10px;
            height: 10px;
            border-radius: 50%;
        }
        .tooltip {
            position: absolute;
            padding: 10px 15px;
            background: rgba(22, 27, 34, 0.95);
            border: 1px solid #30363d;
            border-radius: 8px;
            font-size: 13px;
            pointer-events: none;
            opacity: 0;
            transition: opacity 0.2s;
            max-width: 300px;
            z-index: 1000;
        }
        .tooltip-title {
            font-weight: 600;
            color: #58a6ff;
            margin-bottom: 5px;
        }
        .tooltip-meta {
            color: #8b949e;
            font-size: 11px;
        }
        .tooltip-tags {
            display: flex;
            flex-wrap: wrap;
            gap: 4px;
            margin-top: 8px;
        }
        .tooltip-tag {
            padding: 2px 8px;
            background: rgba(88, 166, 255, 0.1);
            border: 1px solid rgba(88, 166, 255, 0.3);
            border-radius: 4px;
            font-size: 10px;
            color: #58a6ff;
        }
        .search-box {
            position: fixed;
            top: 15px;
            left: 50%;
            transform: translateX(-50%);
            z-index: 101;
        }
        .search-input {
            width: 300px;
            padding: 8px 15px;
            background: rgba(22, 27, 34, 0.9);
            border: 1px solid #30363d;
            border-radius: 20px;
            color: #c9d1d9;
            font-size: 13px;
            outline: none;
        }
        .search-input:focus {
            border-color: #58a6ff;
        }
        .search-input::placeholder {
            color: #6e7681;
        }
        .node-label {
            font-size: 11px;
            fill: #c9d1d9;
            pointer-events: none;
            text-shadow: 0 1px 3px rgba(0,0,0,0.8);
        }
        .back-link {
            position: fixed;
            top: 15px;
            right: 20px;
            z-index: 101;
            padding: 8px 15px;
            background: rgba(22, 27, 34, 0.9);
            border: 1px solid #30363d;
            border-radius: 6px;
            color: #58a6ff;
            text-decoration: none;
            font-size: 13px;
            transition: all 0.2s;
        }
        .back-link:hover {
            background: #30363d;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🕸️ Wiki Knowledge Graph</h1>
        <div class="stats">
            <div class="stat-item">
                <span>Pages:</span>
                <span class="stat-value" id="stat-pages">0</span>
            </div>
            <div class="stat-item">
                <span>Links:</span>
                <span class="stat-value" id="stat-links">0</span>
            </div>
            <div class="stat-item">
                <span>Tags:</span>
                <span class="stat-value" id="stat-tags">0</span>
            </div>
        </div>
    </div>

    <a href="index.md" class="back-link">← Back to Wiki</a>

    <div class="search-box">
        <input type="text" class="search-input" id="search" placeholder="Search pages...">
    </div>

    <div id="graph-container"></div>

    <div class="controls">
        <button class="control-btn" onclick="zoomIn()" title="Zoom In">+</button>
        <button class="control-btn" onclick="zoomOut()" title="Zoom Out">−</button>
        <button class="control-btn" onclick="resetZoom()" title="Reset">⟲</button>
    </div>

    <div class="legend">
        <div class="legend-title">Page Types</div>
        <div class="legend-item">
            <div class="legend-dot" style="background: #58a6ff;"></div>
            <span>Entity</span>
        </div>
        <div class="legend-item">
            <div class="legend-dot" style="background: #7ee787;"></div>
            <span>Concept</span>
        </div>
        <div class="legend-item">
            <div class="legend-dot" style="background: #ffa657;"></div>
            <span>Comparison</span>
        </div>
        <div class="legend-item">
            <div class="legend-dot" style="background: #d2a8ff;"></div>
            <span>Query/Summary</span>
        </div>
        <div class="legend-item">
            <div class="legend-dot" style="background: #8b949e;"></div>
            <span>Note</span>
        </div>
    </div>

    <div class="tooltip" id="tooltip"></div>

    <script>
        // Graph data
        const graphData = ''' + json.dumps(graph_data) + ''';
        
        // Update stats
        document.getElementById('stat-pages').textContent = graphData.stats.total_pages;
        document.getElementById('stat-links').textContent = graphData.stats.total_links;
        document.getElementById('stat-tags').textContent = graphData.stats.total_tags;
        
        // Color scheme for page types
        const typeColors = {
            'entity': '#58a6ff',
            'concept': '#7ee787',
            'comparison': '#ffa657',
            'query': '#d2a8ff',
            'summary': '#d2a8ff',
            'note': '#8b949e',
            'default': '#8b949e'
        };
        
        // Setup SVG
        const container = d3.select('#graph-container');
        const width = window.innerWidth;
        const height = window.innerHeight;
        
        const svg = container.append('svg')
            .attr('width', width)
            .attr('height', height)
            .attr('viewBox', [0, 0, width, height]);
        
        // Add zoom behavior
        const g = svg.append('g');
        const zoom = d3.zoom()
            .scaleExtent([0.1, 4])
            .on('zoom', (event) => g.attr('transform', event.transform));
        svg.call(zoom);
        
        // Create force simulation
        const simulation = d3.forceSimulation(graphData.nodes)
            .force('link', d3.forceLink(graphData.edges)
                .id(d => d.id)
                .distance(100))
            .force('charge', d3.forceManyBody().strength(-300))
            .force('center', d3.forceCenter(width / 2, height / 2))
            .force('collision', d3.forceCollide().radius(30));
        
        // Draw links
        const link = g.append('g')
            .attr('stroke', '#30363d')
            .attr('stroke-opacity', 0.6)
            .selectAll('line')
            .data(graphData.edges)
            .join('line')
            .attr('stroke-width', 1.5);
        
        // Draw nodes
        const node = g.append('g')
            .selectAll('g')
            .data(graphData.nodes)
            .join('g')
            .call(d3.drag()
                .on('start', dragstarted)
                .on('drag', dragged)
                .on('end', dragended));
        
        // Node circles
        node.append('circle')
            .attr('r', d => d.type === 'entity' ? 12 : 8)
            .attr('fill', d => typeColors[d.type] || typeColors.default)
            .attr('stroke', '#0d1117')
            .attr('stroke-width', 2)
            .style('cursor', 'pointer');
        
        // Node labels
        node.append('text')
            .attr('class', 'node-label')
            .attr('x', d => d.type === 'entity' ? 16 : 12)
            .attr('y', 4)
            .text(d => d.title.length > 20 ? d.title.substring(0, 20) + '...' : d.title);
        
        // Tooltip
        const tooltip = d3.select('#tooltip');
        
        node.on('mouseover', (event, d) => {
            tooltip.style('opacity', 1)
                .html(`
                    <div class="tooltip-title">${d.title}</div>
                    <div class="tooltip-meta">Type: ${d.type} | Path: ${d.path}</div>
                    ${d.tags.length ? '<div class="tooltip-tags">' + 
                        d.tags.map(t => `<span class="tooltip-tag">${t}</span>`).join('') + 
                        '</div>' : ''}
                `)
                .style('left', (event.pageX + 10) + 'px')
                .style('top', (event.pageY - 10) + 'px');
        })
        .on('mouseout', () => tooltip.style('opacity', 0))
        .on('click', (event, d) => {
            window.location.href = d.path.replace('.md', '.html');
        });
        
        // Update positions on tick
        simulation.on('tick', () => {
            link
                .attr('x1', d => d.source.x)
                .attr('y1', d => d.source.y)
                .attr('x2', d => d.target.x)
                .attr('y2', d => d.target.y);
            
            node.attr('transform', d => `translate(${d.x},${d.y})`);
        });
        
        // Drag functions
        function dragstarted(event, d) {
            if (!event.active) simulation.alphaTarget(0.3).restart();
            d.fx = d.x;
            d.fy = d.y;
        }
        
        function dragged(event, d) {
            d.fx = event.x;
            d.fy = event.y;
        }
        
        function dragended(event, d) {
            if (!event.active) simulation.alphaTarget(0);
            d.fx = null;
            d.fy = null;
        }
        
        // Zoom controls
        function zoomIn() {
            svg.transition().call(zoom.scaleBy, 1.3);
        }
        
        function zoomOut() {
            svg.transition().call(zoom.scaleBy, 0.7);
        }
        
        function resetZoom() {
            svg.transition().call(zoom.transform, d3.zoomIdentity);
        }
        
        // Search functionality
        document.getElementById('search').addEventListener('input', (e) => {
            const term = e.target.value.toLowerCase();
            if (!term) {
                node.style('opacity', 1);
                link.style('opacity', 0.6);
                return;
            }
            
            const matched = graphData.nodes.filter(n => 
                n.title.toLowerCase().includes(term) ||
                n.id.toLowerCase().includes(term) ||
                n.tags.some(t => t.toLowerCase().includes(term))
            ).map(n => n.id);
            
            node.style('opacity', d => matched.includes(d.id) ? 1 : 0.1);
            link.style('opacity', d => 
                matched.includes(d.source.id) && matched.includes(d.target.id) ? 0.6 : 0.05
            );
        });
        
        // Handle window resize
        window.addEventListener('resize', () => {
            const w = window.innerWidth;
            const h = window.innerHeight;
            svg.attr('width', w).attr('height', h).attr('viewBox', [0, 0, w, h]);
            simulation.force('center', d3.forceCenter(w / 2, h / 2));
            simulation.alpha(0.3).restart();
        });
    </script>
</body>
</html>'''
    
    Path(output_path).write_text(html_template, encoding='utf-8')


def main():
    """Main entry point."""
    script_dir = Path(__file__).parent
    wiki_dir = script_dir.parent.parent  # .github/scripts -> .github -> wiki root
    output_path = wiki_dir / 'graph.html'
    
    print(f"🔍 Scanning wiki directory: {wiki_dir}")
    
    # Build graph
    graph_data = build_graph(wiki_dir)
    
    print(f"📊 Found {graph_data['stats']['total_pages']} pages")
    print(f"🔗 Found {graph_data['stats']['total_links']} links")
    print(f"🏷️  Found {graph_data['stats']['total_tags']} unique tags")
    
    # Generate HTML
    generate_graph_html(graph_data, output_path)
    
    print(f"✅ Graph generated: {output_path}")
    
    # Also generate a JSON version for potential API use
    json_path = wiki_dir / 'graph.json'
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(graph_data, f, indent=2, ensure_ascii=False)
    print(f"✅ Graph data exported: {json_path}")


if __name__ == '__main__':
    main()
