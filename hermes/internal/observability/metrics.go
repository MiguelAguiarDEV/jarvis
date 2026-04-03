package observability

import (
	"fmt"
	"sort"
	"strings"
	"sync"
)

type metricEntry struct {
	Name   string
	Labels map[string]string
	Value  float64
	Help   string
	Type   string
}

type Metrics struct {
	mu      sync.Mutex
	entries map[string]*metricEntry
	started int64
}

func NewMetrics() *Metrics {
	return &Metrics{entries: map[string]*metricEntry{}}
}

func (m *Metrics) Inc(name, help string, labels map[string]string) {
	m.Add(name, help, labels, 1)
}

func (m *Metrics) Add(name, help string, labels map[string]string, delta float64) {
	m.mu.Lock()
	defer m.mu.Unlock()
	entry := m.ensure(name, help, "counter", labels)
	entry.Value += delta
}

func (m *Metrics) Set(name, help string, labels map[string]string, value float64) {
	m.mu.Lock()
	defer m.mu.Unlock()
	entry := m.ensure(name, help, "gauge", labels)
	entry.Value = value
}

func (m *Metrics) ensure(name, help, metricType string, labels map[string]string) *metricEntry {
	key := metricKey(name, labels)
	if entry, ok := m.entries[key]; ok {
		if help != "" {
			entry.Help = help
		}
		entry.Type = metricType
		return entry
	}
	copyLabels := map[string]string{}
	for key, value := range labels {
		copyLabels[key] = value
	}
	entry := &metricEntry{Name: name, Labels: copyLabels, Help: help, Type: metricType}
	m.entries[key] = entry
	return entry
}

func (m *Metrics) Render() string {
	m.mu.Lock()
	defer m.mu.Unlock()
	keys := make([]string, 0, len(m.entries))
	for key := range m.entries {
		keys = append(keys, key)
	}
	sort.Strings(keys)
	var b strings.Builder
	seen := map[string]bool{}
	for _, key := range keys {
		entry := m.entries[key]
		if !seen[entry.Name] {
			if entry.Help != "" {
				b.WriteString(fmt.Sprintf("# HELP %s %s\n", entry.Name, entry.Help))
			}
			metricType := entry.Type
			if metricType == "" {
				metricType = "counter"
			}
			b.WriteString(fmt.Sprintf("# TYPE %s %s\n", entry.Name, metricType))
			seen[entry.Name] = true
		}
		b.WriteString(entry.Name)
		if len(entry.Labels) > 0 {
			b.WriteString("{")
			labelKeys := make([]string, 0, len(entry.Labels))
			for label := range entry.Labels {
				labelKeys = append(labelKeys, label)
			}
			sort.Strings(labelKeys)
			for idx, label := range labelKeys {
				if idx > 0 {
					b.WriteString(",")
				}
				b.WriteString(fmt.Sprintf("%s=%q", label, entry.Labels[label]))
			}
			b.WriteString("}")
		}
		b.WriteString(fmt.Sprintf(" %v\n", entry.Value))
	}
	return b.String()
}

func metricKey(name string, labels map[string]string) string {
	if len(labels) == 0 {
		return name
	}
	keys := make([]string, 0, len(labels))
	for key := range labels {
		keys = append(keys, key)
	}
	sort.Strings(keys)
	parts := make([]string, 0, len(keys)+1)
	parts = append(parts, name)
	for _, key := range keys {
		parts = append(parts, key+"="+labels[key])
	}
	return strings.Join(parts, ",")
}
