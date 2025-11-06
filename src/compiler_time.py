#！ python3

import os
import subprocess
import time

LINUX_SOURCE = '/home/guosy/Kconfig/OS/linux'

import tools


class DAG:
    def __init__(self):
        self.graph = {}

    def add_node(self, name, successors):
        if name in self.graph:
            # raise ValueError("Node already exists.")
            self.graph[name] |= successors
        else:
            self.graph[name] = successors

    def remove_node(self, name):
        if name not in self.graph:
            raise ValueError("Node does not exist.")
        del self.graph[name]
        for node in self.graph:
            if name in self.graph[node]:
                self.graph[node].remove(name)

    def to_directed_graph(self):
        directed_graph = DAG()
        for node in self.graph:
            successors = self.graph[node]
            successor_set = set(successors)
            successor_set.add(node)
            directed_graph.add_node(node, successor_set)
            for successor in successors:
                directed_graph.add_node(successor, {node, successor} | self.graph.get(successor, set()))
        return directed_graph

class UnionFind:
    def __init__(self, nodes):
        self.parent = {node: node for node in nodes}

    def find(self, node):
        if self.parent[node] == node:
            return node
        self.parent[node] = self.find(self.parent[node])
        return self.parent[node]

    def union(self, node1, node2):
        root1 = self.find(node1)
        root2 = self.find(node2)
        if root1 != root2:
            self.parent[root1] = root2

def union_find(dag):
    directed_graph = dag.to_directed_graph()
    nodes = list(directed_graph.graph.keys())
    uf = UnionFind(nodes)
    for node in nodes:
        for successor in directed_graph.graph[node]:
            uf.union(node, successor)
    return uf.parent

def run() -> None:
    
    # subprocess.run('make oldconfig', cwd=LINUX_SOURCE, shell=True)

    begin = time.time()

    subprocess.run('make ARCH=x86 -j8', cwd=LINUX_SOURCE, shell=True)

    subprocess.run('make ARCH=x86 modules -j8', cwd=LINUX_SOURCE, shell=True)

    subprocess.run('make ARCH=x86 install', cwd=LINUX_SOURCE, shell=True)


    cost = time.time() - begin

    print("cost time\t\t{}".format(str(cost)))

    subprocess.run('make clean', cwd=LINUX_SOURCE, shell=False)

def handle_config() -> None:
    dep_path = "./v6.2-x86/v6.2_x86_dep.json"
    kid_path = "./v6.2-x86/v6.2_x86_kid.json"
    # tools.getKid(dep_path, kid_path)
    data = tools.load_json(kid_path)

    graph = DAG()

    for name in data:
        graph.add_node(name, set(data[name]))
    
    parent = union_find(graph)

    result = {}
    for item in parent:
        try:
            result[parent[item]].add(item)
        except KeyError:
            result.update({parent[item]: {item}})

    # print(result)
    max = -1
    target = ""
    for item in result:
        if len(result[item]) > max:
            max = len(result[item])
            target = item

    # print(max)
    # print(target)
    # print(result[target])
    config_path = LINUX_SOURCE + "/.config"
    config = tools.load_config(config_path)

    open_count = -1
    save = []
    for item in result[target]:
        if item in config and config[item] != 'n':
            pass
        save.append(item)
    
    # print("max = " + str(max) + " open_count = " + str(open_count))
    # print(result)

    file = open(config_path, 'a+')
    for item in save:
        file.write("CONFIG_" + item + "=y\n")



if __name__ == '__main__':
    run()
    # handle_config()

    # def_config_path = LINUX_SOURCE + "/.config"
    # handle_config_path = "/home/guosy/Kconfig/.config"

    # def_config = tools.load_config(def_config_path)
    # handleconfig = tools.load_config(handle_config_path)

    # print(len(set(handleconfig) - set(def_config)))