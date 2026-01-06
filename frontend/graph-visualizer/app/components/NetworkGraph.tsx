'use client';

import { useEffect, useRef, useState } from 'react';
import * as d3 from 'd3';

interface SubstepData {
  dirname: string;
  substeps: string[];
}

interface GraphNode extends d3.SimulationNodeDatum {
  id: string;
  tasks: Set<string>;
  frequency: number;
}

interface GraphLink extends d3.SimulationLinkDatum<GraphNode> {
  source: string | GraphNode;
  target: string | GraphNode;
  frequency: number;
}

export default function NetworkGraph() {
  const svgRef = useRef<SVGSVGElement>(null);
  const [data, setData] = useState<SubstepData[]>([]);
  const [loading, setLoading] = useState(true);
  const [darkMode, setDarkMode] = useState(false);
  const [maxEdgeFrequency, setMaxEdgeFrequency] = useState(1);
  const [maxNodeDegree, setMaxNodeDegree] = useState(1);
  const [showLongestPath, setShowLongestPath] = useState(false);
  const [longestPaths, setLongestPaths] = useState<string[][]>([]);
  const [top1000Paths, setTop1000Paths] = useState<string[][]>([]);
  const [selectedPathIndex, setSelectedPathIndex] = useState(0);
  const [isAnimating, setIsAnimating] = useState(false);
  const [animationPathIndex, setAnimationPathIndex] = useState(0);
  const animationIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const [nodeGradient, setNodeGradient] = useState('');
  const [edgeGradient, setEdgeGradient] = useState('');

  useEffect(() => {
    fetch('/all_substeps.json')
      .then((res) => res.json())
      .then((json) => {
        setData(json.data);
        setLoading(false);
      })
      .catch((err) => {
        console.error('Error loading data:', err);
        setLoading(false);
      });
  }, []);

  // Keyboard listener for 'L' key to toggle dark mode, '1-9' for longest paths, and 'j' for animation
  useEffect(() => {
    const handleKeyPress = (event: KeyboardEvent) => {
      if (event.key === 'l' || event.key === 'L') {
        setDarkMode((prev) => !prev);
      } else if (event.key === 'j' || event.key === 'J') {
        // Toggle animation
        setIsAnimating((prev) => !prev);
      } else if (event.key >= '1' && event.key <= '9') {
        const pathNumber = parseInt(event.key);
        const pathIndex = pathNumber - 1;

        if (pathIndex < longestPaths.length) {
          // Stop animation if running
          if (isAnimating) {
            setIsAnimating(false);
          }

          if (showLongestPath && selectedPathIndex === pathIndex) {
            // Toggle off if clicking the same path
            setShowLongestPath(false);
          } else {
            setSelectedPathIndex(pathIndex);
            setShowLongestPath(true);
          }
        }
      }
    };

    window.addEventListener('keydown', handleKeyPress);
    return () => window.removeEventListener('keydown', handleKeyPress);
  }, [longestPaths, showLongestPath, selectedPathIndex, isAnimating]);

  // Animation effect for cycling through top 1000 paths from shortest to longest
  useEffect(() => {
    if (isAnimating && top1000Paths.length > 0) {
      setShowLongestPath(true);

      // Start from shortest (last index in top1000Paths since sorted longest to shortest)
      let currentIndex = top1000Paths.length - 1;
      setAnimationPathIndex(currentIndex);

      animationIntervalRef.current = setInterval(() => {
        currentIndex--;

        if (currentIndex < 0) {
          // Reached the end (longest path), stop animation
          setIsAnimating(false);
          return;
        }

        setAnimationPathIndex(currentIndex);
      }, 100); // 0.1s = 100ms

      return () => {
        if (animationIntervalRef.current) {
          clearInterval(animationIntervalRef.current);
          animationIntervalRef.current = null;
        }
      };
    } else if (!isAnimating && animationIntervalRef.current) {
      // Stop animation
      clearInterval(animationIntervalRef.current);
      animationIntervalRef.current = null;
    }
  }, [isAnimating, top1000Paths]);

  useEffect(() => {
    if (!data.length || !svgRef.current) return;

    // Initial theme colors
    const getTheme = (isDark: boolean) => ({
      nodeStroke: isDark ? '#1e293b' : '#fff',
      svgBg: isDark ? '#000000' : '#ffffff',
    });

    const currentTheme = getTheme(darkMode);

    // Process data to create nodes and links
    const nodeMap = new Map<string, GraphNode>();
    const linkMap = new Map<string, GraphLink>();

    data.forEach((item) => {
      if (item.substeps.length === 0) return;

      item.substeps.forEach((substep, index) => {
        // Add or update node
        if (!nodeMap.has(substep)) {
          nodeMap.set(substep, {
            id: substep,
            tasks: new Set([item.dirname]),
            frequency: 1,
          });
        } else {
          const node = nodeMap.get(substep)!;
          node.tasks.add(item.dirname);
          node.frequency += 1;
        }

        // Add or update link to next substep
        if (index < item.substeps.length - 1) {
          const nextSubstep = item.substeps[index + 1];
          const linkKey = `${substep}→${nextSubstep}`;

          if (!linkMap.has(linkKey)) {
            linkMap.set(linkKey, {
              source: substep,
              target: nextSubstep,
              frequency: 1,
            });
          } else {
            linkMap.get(linkKey)!.frequency += 1;
          }
        }
      });
    });

    const nodes = Array.from(nodeMap.values());
    const links = Array.from(linkMap.values());

    // Calculate node degrees (number of edges connected to each node)
    const nodeDegreeMap = new Map<string, number>();
    nodes.forEach((node) => nodeDegreeMap.set(node.id, 0));
    links.forEach((link) => {
      const sourceId = typeof link.source === 'string' ? link.source : link.source.id;
      const targetId = typeof link.target === 'string' ? link.target : link.target.id;
      nodeDegreeMap.set(sourceId, (nodeDegreeMap.get(sourceId) || 0) + 1);
      nodeDegreeMap.set(targetId, (nodeDegreeMap.get(targetId) || 0) + 1);
    });

    // Add degree to nodes
    nodes.forEach((node) => {
      (node as any).degree = nodeDegreeMap.get(node.id) || 0;
    });

    const calculatedMaxNodeFrequency = d3.max(nodes, (d) => d.frequency) || 1;
    const maxLinkFrequency = d3.max(links, (d) => d.frequency) || 1;

    // Generate gradient strings for legend
    const generateGradient = (steps: number, isDark: boolean, type: 'node' | 'edge') => {
      const colors: string[] = [];
      for (let i = 0; i <= steps; i++) {
        const ratio = steps > 0 ? i / steps : 0;
        let t: number;
        let color: string;
        if (type === 'node') {
          // Node uses (frequency - 1) / (maxFrequency - 1)
          // Map ratio [0,1] to frequency range [1, maxNodeFrequency]
          const freq = 1 + ratio * (calculatedMaxNodeFrequency - 1);
          t = calculatedMaxNodeFrequency > 1 ? (freq - 1) / (calculatedMaxNodeFrequency - 1) : 0;
          color = isDark ? d3.interpolateViridis(t) : d3.interpolateMagma(0.9 - t * 0.4);
        } else {
          // Edge uses (frequency - 1) / (maxFrequency - 1)
          // Map ratio [0,1] to frequency range [1, maxLinkFrequency]
          const freq = 1 + ratio * (maxLinkFrequency - 1);
          t = maxLinkFrequency > 1 ? (freq - 1) / (maxLinkFrequency - 1) : 0;
          color = isDark ? d3.interpolateViridis(t) : d3.interpolateMagma(0.9 - t * 0.4);
        }
        colors.push(color);
      }
      return `linear-gradient(to right, ${colors.join(', ')})`;
    };

    const nodeGrad = generateGradient(10, darkMode, 'node');
    const edgeGrad = generateGradient(10, darkMode, 'edge');

    // Update state for legend
    setMaxNodeDegree(calculatedMaxNodeFrequency);
    setMaxEdgeFrequency(maxLinkFrequency);
    setNodeGradient(nodeGrad);
    setEdgeGradient(edgeGrad);

    // Find all paths in the graph using DFS
    const findAllPaths = () => {
      // Build adjacency list
      const adjacencyList = new Map<string, string[]>();

      nodes.forEach(node => {
        adjacencyList.set(node.id, []);
      });

      links.forEach(link => {
        const sourceId = typeof link.source === 'string' ? link.source : link.source.id;
        const targetId = typeof link.target === 'string' ? link.target : link.target.id;
        adjacencyList.get(sourceId)?.push(targetId);
      });

      // DFS to find all paths from a given node
      const allPathsFromNode: string[][] = [];

      const dfs = (node: string, visited: Set<string>, path: string[]) => {
        visited.add(node);
        path.push(node);

        const neighbors = adjacencyList.get(node) || [];
        let hasUnvisitedNeighbor = false;

        for (const neighbor of neighbors) {
          if (!visited.has(neighbor)) {
            hasUnvisitedNeighbor = true;
            dfs(neighbor, visited, [...path]);
          }
        }

        // If no unvisited neighbors, this is a terminal path
        if (!hasUnvisitedNeighbor) {
          allPathsFromNode.push([...path]);
        }

        visited.delete(node);
      };

      // Try starting from all nodes to collect all maximal paths
      nodes.forEach(node => {
        dfs(node.id, new Set(), []);
      });

      // Get unique paths
      const uniquePaths = new Map<string, string[]>();
      allPathsFromNode.forEach(path => {
        const key = path.join('→');
        if (!uniquePaths.has(key)) {
          uniquePaths.set(key, path);
        }
      });

      // Sort paths by length descending (longest to shortest)
      const allSortedPaths = Array.from(uniquePaths.values())
        .sort((a, b) => b.length - a.length);

      const top9Paths = allSortedPaths.slice(0, 9);
      const top1000Paths = allSortedPaths.slice(0, 1000);

      return { allPaths: allSortedPaths, top9: top9Paths, top1000: top1000Paths };
    };

    const { allPaths: allFoundPaths, top9, top1000 } = findAllPaths();
    console.log(`Found ${allFoundPaths.length} total unique paths`);
    console.log('Top 9 longest paths:');
    top9.forEach((path, idx) => {
      console.log(`${idx + 1}. Length ${path.length}:`, path);
    });
    console.log(`Will animate through top ${top1000.length} paths`);
    console.log('Shortest in top 1000:', top1000[top1000.length - 1]?.length, 'nodes');
    console.log('Longest path:', top1000[0]?.length, 'nodes');
    setTop1000Paths(top1000);
    setLongestPaths(top9);

    // Clear previous SVG content
    d3.select(svgRef.current).selectAll('*').remove();

    // Set up SVG
    const width = 1400;
    const height = 900;
    const svg = d3
      .select(svgRef.current)
      .attr('width', width)
      .attr('height', height)
      .attr('viewBox', [0, 0, width, height])
      .style('background-color', currentTheme.svgBg);

    // Add zoom behavior
    const g = svg.append('g');

    svg.call(
      d3.zoom<SVGSVGElement, unknown>()
        .scaleExtent([0.1, 4])
        .on('zoom', (event) => {
          g.attr('transform', event.transform);
        }) as any
    );

    // Create arrow markers for each frequency level with matching colors
    const defs = svg.append('defs');
    for (let i = 1; i <= maxLinkFrequency; i++) {
      const t = maxLinkFrequency > 1 ? (i - 1) / (maxLinkFrequency - 1) : 0;
      // Use magma (0.9 to 0.5) for light mode: pale→medium pink, viridis for dark mode
      const color = darkMode ? d3.interpolateViridis(t) : d3.interpolateMagma(0.9 - t * 0.4);

      defs
        .append('marker')
        .attr('id', `arrow-${i}`)
        .attr('viewBox', '0 -5 10 10')
        .attr('refX', 20)
        .attr('refY', 0)
        .attr('markerWidth', 6)
        .attr('markerHeight', 6)
        .attr('orient', 'auto')
        .append('path')
        .attr('d', 'M0,-5L10,0L0,5')
        .attr('class', `arrow-path-${i}`)
        .attr('fill', color);
    }

    // Create force simulation with 4x attraction and 2x centering force
    const simulation = d3
      .forceSimulation<GraphNode>(nodes)
      .force(
        'link',
        d3
          .forceLink<GraphNode, GraphLink>(links)
          .id((d) => d.id)
          .distance(25) // Reduced from 50 to 25 for 4x attraction (2x more than before)
      )
      .force('charge', d3.forceManyBody().strength(-300))
      .force('center', d3.forceCenter(width / 2, height / 2).strength(2)) // 2x centering force
      .force('collision', d3.forceCollide().radius(30));

    // Create links with color scheme (magma 0.9 to 0.5 for light, viridis for dark)
    const link = g
      .append('g')
      .selectAll('line')
      .data(links)
      .join('line')
      .attr('class', 'graph-link')
      .attr('data-frequency', (d) => d.frequency)
      .attr('data-max-frequency', maxLinkFrequency)
      .attr('data-source', (d) => typeof d.source === 'string' ? d.source : d.source.id)
      .attr('data-target', (d) => typeof d.target === 'string' ? d.target : d.target.id)
      .attr('stroke', (d) => {
        const t = maxLinkFrequency > 1 ? (d.frequency - 1) / (maxLinkFrequency - 1) : 0;
        // Use magma (0.9 to 0.5) for light mode: pale→medium pink, viridis for dark mode
        return darkMode ? d3.interpolateViridis(t) : d3.interpolateMagma(0.9 - t * 0.4);
      })
      .attr('stroke-width', 2)
      .attr('stroke-opacity', 0.8)
      .attr('marker-end', (d) => `url(#arrow-${d.frequency})`);

    // Create tooltip
    const tooltip = d3
      .select('body')
      .append('div')
      .attr('class', 'graph-tooltip')
      .style('position', 'absolute')
      .style('visibility', 'hidden')
      .style('background-color', darkMode ? 'rgba(30, 41, 59, 0.95)' : 'rgba(0, 0, 0, 0.9)')
      .style('color', 'white')
      .style('padding', '12px')
      .style('border-radius', '8px')
      .style('font-size', '12px')
      .style('max-width', '400px')
      .style('pointer-events', 'none')
      .style('z-index', '1000')
      .style('line-height', '1.4')
      .style('border', darkMode ? '1px solid rgba(96, 165, 250, 0.3)' : 'none');

    // Create nodes with colors based on frequency (magma 0.9 to 0.5 for light, viridis for dark)
    const node = g
      .append('g')
      .selectAll('circle')
      .data(nodes)
      .join('circle')
      .attr('class', 'graph-node')
      .attr('r', 16)
      .attr('data-frequency', (d) => d.frequency)
      .attr('data-max-frequency', calculatedMaxNodeFrequency)
      .attr('data-degree', (d: any) => d.degree)
      .attr('fill', (d) => {
        const t = calculatedMaxNodeFrequency > 1 ? (d.frequency - 1) / (calculatedMaxNodeFrequency - 1) : 0;
        // Use magma (0.9 to 0.5) for light mode: pale→medium pink, viridis for dark mode
        return darkMode ? d3.interpolateViridis(t) : d3.interpolateMagma(0.9 - t * 0.4);
      })
      .attr('stroke', currentTheme.nodeStroke)
      .attr('stroke-width', 2)
      .style('cursor', 'pointer')
      .call(
        d3
          .drag<SVGCircleElement, GraphNode>()
          .on('start', (event, d) => {
            if (!event.active) simulation.alphaTarget(0.3).restart();
            d.fx = d.x;
            d.fy = d.y;
          })
          .on('drag', (event, d) => {
            d.fx = event.x;
            d.fy = event.y;
          })
          .on('end', (event, d) => {
            if (!event.active) simulation.alphaTarget(0);
            d.fx = null;
            d.fy = null;
          })
      );

    // Add hover effects
    node
      .on('mouseover', (event, d: any) => {
        const tasks = Array.from(d.tasks);
        const displayTasks = tasks.slice(0, 10);
        const remaining = tasks.length - displayTasks.length;

        tooltip
          .style('visibility', 'visible')
          .html(
            `<div style="font-weight: bold; margin-bottom: 8px; border-bottom: 1px solid rgba(255,255,255,0.3); padding-bottom: 4px;">${d.id}</div>
             <div style="margin-bottom: 4px;"><strong>Frequency:</strong> ${d.frequency}</div>
             <div style="margin-bottom: 4px;"><strong>Connections:</strong> ${d.degree} edges</div>
             <div style="margin-bottom: 4px;"><strong>Tasks (${tasks.length}):</strong></div>
             <div style="max-height: 200px; overflow-y: auto; font-size: 10px;">
               ${displayTasks.map((task) => `<div style="margin: 2px 0;">• ${task}</div>`).join('')}
               ${remaining > 0 ? `<div style="margin-top: 4px; font-style: italic;">...and ${remaining} more</div>` : ''}
             </div>`
          );

        // Highlight connected nodes and links
        link
          .attr('stroke-opacity', (l) =>
            (l.source as GraphNode).id === d.id || (l.target as GraphNode).id === d.id ? 1 : 0.1
          )
          .attr('stroke-width', (l) =>
            (l.source as GraphNode).id === d.id || (l.target as GraphNode).id === d.id ? 3 : 2
          );

        node.attr('opacity', (n) => {
          if (n.id === d.id) return 1;
          const isConnected = links.some(
            (l) =>
              ((l.source as GraphNode).id === d.id && (l.target as GraphNode).id === n.id) ||
              ((l.target as GraphNode).id === d.id && (l.source as GraphNode).id === n.id)
          );
          return isConnected ? 1 : 0.2;
        });
      })
      .on('mousemove', (event) => {
        tooltip
          .style('top', event.pageY + 15 + 'px')
          .style('left', event.pageX + 15 + 'px');
      })
      .on('mouseout', () => {
        tooltip.style('visibility', 'hidden');
        link.attr('stroke-opacity', 0.8).attr('stroke-width', 2);
        node.attr('opacity', 1);
      });

    // Update positions on each tick
    simulation.on('tick', () => {
      link
        .attr('x1', (d) => (d.source as GraphNode).x!)
        .attr('y1', (d) => (d.source as GraphNode).y!)
        .attr('x2', (d) => (d.target as GraphNode).x!)
        .attr('y2', (d) => (d.target as GraphNode).y!);

      node.attr('cx', (d) => d.x!).attr('cy', (d) => d.y!);
    });

    // Cleanup
    return () => {
      simulation.stop();
      tooltip.remove();
    };
  }, [data]);

  // Separate effect to update theme colors without re-rendering the graph
  useEffect(() => {
    if (!svgRef.current) return;

    const theme = {
      nodeStroke: darkMode ? '#1e293b' : '#fff',
      svgBg: darkMode ? '#000000' : '#ffffff',
    };

    // Regenerate gradients for legend
    const generateGradient = (steps: number, isDark: boolean, type: 'node' | 'edge') => {
      const colors: string[] = [];
      for (let i = 0; i <= steps; i++) {
        const ratio = steps > 0 ? i / steps : 0;
        let t: number;
        let color: string;
        if (type === 'node') {
          // Node uses (frequency - 1) / (maxFrequency - 1)
          // Map ratio [0,1] to frequency range [1, maxNodeFrequency]
          const freq = 1 + ratio * (maxNodeDegree - 1);
          t = maxNodeDegree > 1 ? (freq - 1) / (maxNodeDegree - 1) : 0;
          color = isDark ? d3.interpolateViridis(t) : d3.interpolateMagma(0.9 - t * 0.4);
        } else {
          // Edge uses (frequency - 1) / (maxFrequency - 1)
          // Map ratio [0,1] to frequency range [1, maxLinkFrequency]
          const freq = 1 + ratio * (maxEdgeFrequency - 1);
          t = maxEdgeFrequency > 1 ? (freq - 1) / (maxEdgeFrequency - 1) : 0;
          color = isDark ? d3.interpolateViridis(t) : d3.interpolateMagma(0.9 - t * 0.4);
        }
        colors.push(color);
      }
      return `linear-gradient(to right, ${colors.join(', ')})`;
    };

    setNodeGradient(generateGradient(10, darkMode, 'node'));
    setEdgeGradient(generateGradient(10, darkMode, 'edge'));

    // Update SVG background
    d3.select(svgRef.current).style('background-color', theme.svgBg);

    // Update node strokes and fills with appropriate colormap
    d3.selectAll('.graph-node').each(function () {
      const frequency = +(this as SVGCircleElement).getAttribute('data-frequency')!;
      const maxFrequency = +(this as SVGCircleElement).getAttribute('data-max-frequency')!;
      const t = maxFrequency > 1 ? (frequency - 1) / (maxFrequency - 1) : 0;
      const color = darkMode ? d3.interpolateViridis(t) : d3.interpolateMagma(0.9 - t * 0.4);

      d3.select(this)
        .attr('fill', color)
        .attr('stroke', theme.nodeStroke);
    });

    // Update all links with appropriate colormap
    d3.selectAll('.graph-link').each(function () {
      const frequency = +(this as SVGLineElement).getAttribute('data-frequency')!;
      const maxFreq = +(this as SVGLineElement).getAttribute('data-max-frequency')!;
      const t = maxFreq > 1 ? (frequency - 1) / (maxFreq - 1) : 0;
      const color = darkMode ? d3.interpolateViridis(t) : d3.interpolateMagma(0.9 - t * 0.4);

      d3.select(this).attr('stroke', color);
    });

    // Update arrow colors with appropriate colormap
    d3.selectAll('[class^="arrow-path-"]').each(function () {
      const className = (this as SVGPathElement).getAttribute('class')!;
      const frequency = parseInt(className.split('-')[2]);
      const maxFreq = maxEdgeFrequency;
      const t = maxFreq > 1 ? (frequency - 1) / (maxFreq - 1) : 0;
      const color = darkMode ? d3.interpolateViridis(t) : d3.interpolateMagma(0.9 - t * 0.4);

      d3.select(this).attr('fill', color);
    });

    // Update tooltip
    d3.selectAll('.graph-tooltip')
      .style('background-color', darkMode ? 'rgba(30, 41, 59, 0.95)' : 'rgba(0, 0, 0, 0.9)')
      .style('border', darkMode ? '1px solid rgba(96, 165, 250, 0.3)' : 'none');
  }, [darkMode, maxEdgeFrequency]);

  // Separate effect to highlight longest path
  useEffect(() => {
    if (!svgRef.current) return;

    // Use animation path if animating, otherwise use selected path from top 9
    const currentPath = isAnimating
      ? (top1000Paths[animationPathIndex] || [])
      : (longestPaths[selectedPathIndex] || []);

    // Check if a link is part of the current path
    const isInCurrentPath = (source: string, target: string) => {
      for (let i = 0; i < currentPath.length - 1; i++) {
        if (currentPath[i] === source && currentPath[i + 1] === target) {
          return true;
        }
      }
      return false;
    };

    if (showLongestPath && currentPath.length > 0) {
      // Highlight edges in the current path
      d3.selectAll('.graph-link').each(function () {
        const source = (this as SVGLineElement).getAttribute('data-source')!;
        const target = (this as SVGLineElement).getAttribute('data-target')!;

        if (isInCurrentPath(source, target)) {
          // Highlight this edge
          d3.select(this)
            .attr('stroke', '#00ff00')
            .attr('stroke-width', 5)
            .attr('stroke-opacity', 1);
        } else {
          // Dim other edges
          d3.select(this)
            .attr('stroke-opacity', 0.1);
        }
      });

      // Highlight nodes in the current path
      d3.selectAll('.graph-node').each(function (d: any) {
        if (currentPath.includes(d.id)) {
          d3.select(this)
            .attr('stroke', '#00ff00')
            .attr('stroke-width', 4)
            .attr('opacity', 1);
        } else {
          d3.select(this).attr('opacity', 0.2);
        }
      });
    } else {
      // Reset to normal styling
      const theme = {
        nodeStroke: darkMode ? '#1e293b' : '#fff',
      };

      d3.selectAll('.graph-link').each(function () {
        const frequency = +(this as SVGLineElement).getAttribute('data-frequency')!;
        const maxFreq = +(this as SVGLineElement).getAttribute('data-max-frequency')!;
        const t = maxFreq > 1 ? (frequency - 1) / (maxFreq - 1) : 0;
        const color = darkMode ? d3.interpolateViridis(t) : d3.interpolateMagma(0.9 - t * 0.4);

        d3.select(this)
          .attr('stroke', color)
          .attr('stroke-width', 2)
          .attr('stroke-opacity', 0.8);
      });

      d3.selectAll('.graph-node').each(function () {
        const frequency = +(this as SVGCircleElement).getAttribute('data-frequency')!;
        const maxFrequency = +(this as SVGCircleElement).getAttribute('data-max-frequency')!;
        const t = maxFrequency > 1 ? (frequency - 1) / (maxFrequency - 1) : 0;
        const color = darkMode ? d3.interpolateViridis(t) : d3.interpolateMagma(0.9 - t * 0.4);

        d3.select(this)
          .attr('fill', color)
          .attr('stroke', theme.nodeStroke)
          .attr('stroke-width', 2)
          .attr('opacity', 1);
      });
    }
  }, [showLongestPath, longestPaths, top1000Paths, selectedPathIndex, animationPathIndex, isAnimating, darkMode]);

  if (loading) {
    return (
      <div className={`flex h-screen items-center justify-center ${darkMode ? 'bg-black text-white' : 'bg-white text-gray-900'}`}>
        <div className="text-lg">Loading network graph...</div>
      </div>
    );
  }

  return (
    <div className={`flex flex-col h-screen transition-colors ${darkMode ? 'bg-black' : 'bg-gray-50'}`}>
      <div className={`shadow-sm p-4 border-b transition-colors ${darkMode ? 'bg-zinc-900 border-zinc-800' : 'bg-white border-gray-200'}`}>
        <div className="flex items-center justify-between">
          <h1 className={`text-2xl font-bold ${darkMode ? 'text-white' : 'text-gray-900'}`}>
            Substeps Network Graph
          </h1>
          <div className="flex gap-2">
            <div className={`text-xs px-3 py-1 rounded-full ${darkMode ? 'bg-slate-700 text-blue-400' : 'bg-gray-100 text-gray-600'}`}>
              Press L to toggle theme
            </div>
            <div className={`text-xs px-3 py-1 rounded-full ${showLongestPath ? (darkMode ? 'bg-green-700 text-green-200' : 'bg-green-200 text-green-800') : (darkMode ? 'bg-slate-700 text-blue-400' : 'bg-gray-100 text-gray-600')}`}>
              Press 1-{longestPaths.length} to show longest paths {showLongestPath && !isAnimating ? `(showing #${selectedPathIndex + 1})` : ''}
            </div>
            <div className={`text-xs px-3 py-1 rounded-full ${isAnimating ? (darkMode ? 'bg-purple-700 text-purple-200' : 'bg-purple-200 text-purple-800') : (darkMode ? 'bg-slate-700 text-blue-400' : 'bg-gray-100 text-gray-600')}`}>
              Press J to animate {isAnimating ? `(${top1000Paths.length - animationPathIndex}/${top1000Paths.length})` : '(top 1000 paths)'}
            </div>
          </div>
        </div>
        <p className={`text-sm mt-1 ${darkMode ? 'text-gray-300' : 'text-gray-600'}`}>
          Hover over nodes to see task details. Drag nodes to rearrange. Scroll to zoom.
          {isAnimating && top1000Paths[animationPathIndex] && (
            <span className={`ml-2 font-semibold ${darkMode ? 'text-purple-300' : 'text-purple-600'}`}>
              Currently showing path with {top1000Paths[animationPathIndex].length} nodes
            </span>
          )}
        </p>
        <div className={`flex flex-col gap-3 mt-3 text-xs ${darkMode ? 'text-gray-300' : 'text-gray-700'}`}>
          <div className="flex items-center gap-3">
            <div className="flex flex-col">
              <div className="flex items-center gap-2 mb-1">
                <span className="font-semibold">Node color = frequency:</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-[10px]">1</span>
                <div className="flex h-3 w-32 rounded overflow-hidden" style={{
                  background: nodeGradient
                }}></div>
                <span className="text-[10px]">{maxNodeDegree}</span>
                <span className="ml-1">occurrences</span>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div className="flex flex-col">
              <div className="flex items-center gap-2 mb-1">
                <span className="font-semibold">Edge color = frequency:</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-[10px]">1</span>
                <div className="flex h-3 w-32 rounded overflow-hidden" style={{
                  background: edgeGradient
                }}></div>
                <span className="text-[10px]">{maxEdgeFrequency}</span>
                <span className="ml-1">occurrences</span>
              </div>
            </div>
          </div>
          {longestPaths.length > 0 && (
            <div className="flex items-center gap-3 mt-2">
              <div className="flex flex-col">
                <div className="flex items-center gap-2 mb-1">
                  <span className="font-semibold">Available paths:</span>
                </div>
                <div className="flex items-center gap-2 flex-wrap">
                  {longestPaths.map((path, idx) => (
                    <div
                      key={idx}
                      className={`text-[10px] px-2 py-1 rounded ${
                        showLongestPath && selectedPathIndex === idx
                          ? isAnimating
                            ? darkMode
                              ? 'bg-purple-700 text-purple-200 font-bold'
                              : 'bg-purple-200 text-purple-800 font-bold'
                            : darkMode
                            ? 'bg-green-700 text-green-200 font-bold'
                            : 'bg-green-200 text-green-800 font-bold'
                          : darkMode
                          ? 'bg-slate-700 text-slate-300'
                          : 'bg-gray-200 text-gray-700'
                      }`}
                    >
                      {idx + 1}: {path.length} nodes
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
      <div className="flex-1 overflow-hidden">
        <svg ref={svgRef} className="w-full h-full"></svg>
      </div>
    </div>
  );
}
