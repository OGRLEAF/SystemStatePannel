

ws = new WebSocket('ws://192.168.3.66:8081');

ws.onmessage = function(evt){
  var data = JSON.parse(evt.data);
  var cpu = [data.cpu.user, data.cpu.system, 100 - data.cpu.user - data.cpu.system];
  var mem = data.mem;
  //console.log(data)
  // cpu
  var cpu_total = document.getElementById('cpu-total')
  cpu_total.innerText = data.cpu.count
  var cpu_bar = document.getElementById("cpu-info").getElementsByTagName('div');  
  var cpu_sample_bar = document.getElementsByClassName("progress-sample");  
  for(var i=0; i<=2; i++){
    cpu_bar[i].style.cssText = 'width:' + cpu[i].toFixed(1) + '%'
    cpu_bar[i].innerText = cpu[i].toFixed(1) + '%'  
    cpu_sample_bar[i].lastElementChild.innerText = cpu[i].toFixed(1) + '%'  
  }
  // memory
  var mem_bar = document.getElementById("mem-info").getElementsByTagName('div')[0];  
  mem_bar.innerText = 'Used: ' + (mem.used/1024**3).toFixed(2) + "GB"
  mem_bar.style.cssText = 'width:' + mem.used/mem.total*100 + '%'
  mem_bar.nextElementSibling.innerHTML = "Free: " + ((mem.total - mem.used)/1024**3).toFixed(2) + "GB"
  var mem_available_percent = mem.available/mem.total*100
  mem_bar.nextElementSibling.style.cssText = "width:" + mem_available_percent + "%"
  if(mem_available_percent<=20){
    $('#available-mem').popover('show')
  }else{
    $('#available-mem').popover('hide')
  }
  var mem_total_div = document.getElementById('mem-total')
  mem_total_div.innerText = (mem.total/1024**3).toFixed(2) + "GB"
  // disk
  disk.load(chart_disk, data.disk.slice(2,4), data.time, ['Read', 'Write'],'I/O')
  // network
  net.load(chart_network, data.net, data.time, ['Out', 'In'],'Traffic')
  /*var users_tag = document.getElementById('current-users')
  users_tag.innerHTML = ''
  for(user of data.users){
    var node = document.createElement('div')
    node.innerText = user[0]
    node.className = "current-user"
    users_tag.appendChild(node)
  }
  console.log(data.users)
  */
}
init_echarts = function(id){
  var dom = document.getElementById(id);
  var myChart = echarts.init(dom, 'dark');
  var app = {};
  option = null;
  return myChart
}

chart_disk = init_echarts('disk-chart');
chart_network = init_echarts('network-chart');

function timeSeriesData(){
  var obj = {}
  obj.load = function(chart, data, time, legend, label) {
    var speed = [0, 0]
    var tmp = this.tmp
    var write_bytes = data[1]
    var read_bytes = data[0]
    this.tmp = {
      count:[write_bytes, read_bytes],
      time: time} 
    
    if(tmp != null){
      speed = [(write_bytes - tmp.count[0])/(time - tmp.time), 
                  (read_bytes - tmp.count[1])/(time - tmp.time)]
    }
    
    this.stamp.x.push(time)
    this.stamp.y.push(speed)
    if(this.stamp.x.length>=10){
      this.stamp.x = this.stamp.x.slice(-10)
      this.stamp.y = this.stamp.y.slice(-10)
    }
    //console.log(this.tmp)
    load_echarts(chart, this.stamp, legend, label)
  }
  obj.tmp = null;
  obj.stamp = {
    x: [],
    y: []
  }
  return obj
}

load_echarts = function(chart, data, legend, y_label){
  // 根据数据选择合适的单位
  var [unit, y_axis] = indexValue(data.y)
  //console.log([data.y])
  option = {
    grid: {
        left: '3%',
        right: '4%',
        bottom: '3%',
        containLabel: true
    },
    legend:{
      data: legend
    },
    xAxis: {

        type: 'category',
        boundaryGap: false,
        data: data.x.map(a=>timestampToTime(a)),
        axisLabel:{
        margin:0,
        }
    },
    yAxis: {
        name: y_label + ' ' + unit,
        type: 'value',
        nameLocation: 'center',
        nameGap:-20,
        scale: true
    },
    series: [
        {
          name: legend[0],
          type:'line',
          stack: '总量',
          data: y_axis.map(a=>a[1].toFixed(1))
        },
       {
          name:legend[1],
          type:'line',
          stack: '总量',
          data: y_axis.map(a=>a[0].toFixed(1))
      }
      ],
      textStyle:{
        color:'white'
      },
      grid:{
        right:'9%',
        left:'11%',
        top:"6%",
        bottom:'20px'
      }
}
;
if (option && typeof option === "object") {
    chart.setOption(option, true);
}
}

window.onload=function(){
  //定时器每秒调用一次fnDate()
  setInterval(function(){
    fnDate();
    },
    1000);
    }
   
  //js 获取当前时间
  function fnDate(){
    var oDiv=document.getElementById("time");
    var date=new Date();
    var hours=date.getHours();//小时
    var minute=date.getMinutes();//分
    var second=date.getSeconds();//秒
    var time = date.toDateString() + "  " + hours +":"+ minute +":"+fnW(second);
    oDiv.innerHTML=time;
    }
  //补位 当某个字段不是两位数时补0
  function fnW(str){
    var num;
    str>=10?num=str:num="0"+str;
    return num;
    } 

// 时间戳格式化
function timestampToTime(timestamp) {
  var date = new Date(timestamp * 1000);//时间戳为10位需*1000，时间戳为13位的话不需乘1000
    var Y = date.getFullYear() + '-';
    var M = (date.getMonth()+1 < 10 ? '0'+(date.getMonth()+1) : date.getMonth()+1) + '-';
    var D = (date.getDate() < 10 ? '0'+date.getDate() : date.getDate()) + ' ';
    var h = (date.getHours() < 10 ? '0'+date.getHours() : date.getHours()) + ':';
    var m = (date.getMinutes() < 10 ? '0'+date.getMinutes() : date.getMinutes()) + ':';
    var s = (date.getSeconds() < 10 ? '0'+date.getSeconds() : date.getSeconds());
    return h + m + s;
}
// 为图表选择合适的单位、分度值, 参数是一个一维数组，每个元素的单位是bytes/s
function indexValue(data){
  // 获取最大值
  var pool = []
  console.log(data)
  for(var item of data){
    for(var e of item){
      pool.push(e)
      //console.log(e)
    }
    
  }
  //console.log(pool)
  var max_value = pool.sort(function(a,b){return b-a})[0]
  var unit = null
  var res = []
  
  if(max_value <= 1024){
    unit = 'b/s'
    res = data
  }else if(1024 <= max_value && max_value< 1024**2){
    unit = 'Kb/s'
    res = data.map(i=>[i[0]/1024,i[1]/1024])
  }else if(1024**2 <= max_value && max_value < 1024**3){
    unit = "Mb/s"
    res = data.map(i=>[i[0]/1024**2,i[1]/1024**2])
  }else{
    unit = "GB/s"
    res = data.map(i=>[i[0]/1024**3,i[1]/1024**3])
  }
  return [unit,res]
}
var disk = timeSeriesData()
var net = timeSeriesData()
