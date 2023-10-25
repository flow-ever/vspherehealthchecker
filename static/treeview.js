function gen_tree(childs){
  var html = ''
  childs.forEach(el => {
      html+=`<details open>
          <summary>
              <span class="tree-item" title="${el.name}"><a href="/${el.type}/${el.name}">${el.name}</a></span>
          </summary>`
      // console.log(html)
      if (el.children && el.children.length) {
          html += gen_tree(el.children) // 如果有chidren就继续遍历
      }
      html+= `</details>`
  })
  return html;
  }

function gen_org_tree(childs){

    var html = '<ul>'
    childs.forEach(el => {
        html+=`
            <li>
                <a href="/${el.type}/${el.name}">${el.name}</a>
            `
        
        if (el.children && el.children.length) {

            html += gen_org_tree(el.children) // 如果有chidren就继续遍历
        }
        
    })
    html+= `</li></ul>`
    return html;
    console.log(html)
}

function includenav(){    
    document.writeln("<div id=\'head_memu\'>");
    document.writeln("    <ul id=\'nav_head\'>");
    document.writeln("        <li></li><a href=\'/datacenter\'>数据中心</a></li>");
    document.writeln("        <li><a href=\'/cluster/Cluster'>群集状况</a></li>");    
    document.writeln("        <li></li><a href=\'/virtualmachine\'>虚拟机总览</a></li>");
    document.writeln("    </ul>");
    document.writeln("</div>");
}

