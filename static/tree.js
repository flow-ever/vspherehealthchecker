const treeData=[
    {
        'name': 'Datacenter', 
        'children':
            [
                {
                    'name': 'Cluster', 
                    'children': 
                        [ 
                            {'name': '192.168.10.233', 'children': []}, 
                            {'name': '192.168.10.233', 'children': []}, 
                            {'name': '192.168.10.233', 'children': []}, 
                            {'name': '192.168.10.233', 'children': []}
                        ]
                }
            ]
    }
]
function gen_tree(childs){
var html = ''
childs.forEach(el => {
    html+=`<details>
    <summary>
        <span class="tree-item" title="${el.name}">${el.name}</span>
    </summary>`
    console.log(el.name)
    if (el.children && el.children.length) {
        html += gen_tree(el.children) // 如果有chidren就继续遍历
    }
    html+= `</details>`
})
return html;
console.log(html)
}

var tree=document.getElementById('tree')
tree.innerHTML=gen_tree(treeData)