function showStemGraph(childId, stemData) {
    const ctx = document.getElementById(`stem-graph-${childId}`).getContext('2d');
    
    const stemCodes = ['science', 'technology', 'engineering', 'math'];
    const data = stemCodes.map(code => stemData[code]);
    const backgroundColor = data.map(score => score >= 50 ? 'rgba(75, 192, 192, 0.2)' : 'rgba(255, 99, 132, 0.2)');
    const borderColor = data.map(score => score >= 50 ? 'rgb(75, 192, 192)' : 'rgb(255, 99, 132)');

    new Chart(ctx, {
        type: 'radar',
        data: {
            labels: stemCodes.map(code => code.charAt(0).toUpperCase() + code.slice(1)),
            datasets: [{
                label: 'STEM Levels',
                data: data,
                fill: true,
                backgroundColor: backgroundColor,
                borderColor: borderColor,
                pointBackgroundColor: borderColor,
                pointBorderColor: '#fff',
                pointHoverBackgroundColor: '#fff',
                pointHoverBorderColor: borderColor
            }]
        },
        options: {
            elements: {
                line: {
                    borderWidth: 3
                }
            },
            scales: {
                r: {
                    angleLines: {
                        display: false
                    },
                    suggestedMin: 0,
                    suggestedMax: 100
                }
            },
            plugins: {
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return `${context.label}: ${context.raw}%`;
                        }
                    }
                }
            }
        }
    });
}

document.addEventListener('DOMContentLoaded', function() {
    const childNames = document.querySelectorAll('.child-name');
    childNames.forEach(childName => {
        childName.addEventListener('click', function() {
            const childId = this.dataset.childId;
            const graphContainer = document.getElementById(`graph-container-${childId}`);
            
            if (graphContainer.style.display === 'none') {
                graphContainer.style.display = 'block';
                // Fetch STEM data for the child
                fetch(`/api/child_stem_levels/${childId}`)
                    .then(response => response.json())
                    .then(data => {
                        showStemGraph(childId, data);
                    });
            } else {
                graphContainer.style.display = 'none';
            }
        });
    });
});
